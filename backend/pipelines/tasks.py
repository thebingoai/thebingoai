"""Celery tasks for Pipeline scheduling and execution (Phase 2)."""
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

logger = logging.getLogger(__name__)

# Register beat schedule entry at import time (same pattern as GA4 tasks)
def _register_beat():
    try:
        from backend.tasks.upload_tasks import celery_app
        celery_app.conf.beat_schedule.setdefault("dispatch-pipelines", {
            "task": "dispatch_pipelines",
            "schedule": 60.0,  # every 60 seconds — croniter gates actual per-pipeline execution
        })
        celery_app.conf.beat_schedule.setdefault("pipeline-health-check", {
            "task": "pipeline_health_check",
            "schedule": 300.0,  # every 300 seconds (5 minutes)
        })
    except Exception:
        pass  # Worker processes may not have beat_schedule yet

_register_beat()


def _queue_depth(queue: str) -> "int | str":
    """Broker backlog for a queue name. Best-effort — never breaks the caller."""
    try:
        import redis as syncredis
        from backend.config import settings

        rc = syncredis.from_url(settings.celery_broker_url)
        try:
            return rc.llen(queue)
        finally:
            rc.close()
    except Exception:
        return "?"


@shared_task(name="dispatch_pipelines")
def dispatch_pipelines():
    """Beat dispatcher: runs every 60s, fires run_pipeline for due pipelines.

    Gated by the new_pipelines feature flag per Org.
    """
    from sqlalchemy import text
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline, PipelineSchedule
    from backend.config.feature_flags import enabled as flag_enabled
    from backend.utils.cron import compute_next_run

    db = SessionLocal()
    now = datetime.now(timezone.utc)
    dispatched = 0

    try:
        due = (
            db.query(Pipeline)
            .filter(
                Pipeline.enabled == True,
                Pipeline.next_run_at <= now,
                Pipeline.cron.isnot(None),
            )
            .all()
        )

        for pipeline in due:
            try:
                # Gate: check new_pipelines flag for the Org owning this pipeline
                # Owner scope_kind must be "org" for flag lookup; user-scoped pipelines
                # always run (no org to gate on).
                if pipeline.owner_scope_kind == "org":
                    if not flag_enabled(pipeline.owner_scope_id, "new_pipelines"):
                        continue

                run_pipeline_task.delay(pipeline.id, "cron", None)
                dispatched += 1

                # Advance next_run_at, honoring the pipeline's configured timezone
                pipeline.next_run_at = compute_next_run(
                    pipeline.cron,
                    pipeline.timezone or "UTC",
                    now_utc=now,
                )

            except Exception as exc:
                logger.error("dispatch_pipelines: failed for pipeline %s: %s", pipeline.id, exc)

        # New model: fire due schedules (each runs its own table subset).
        due_schedules = (
            db.query(PipelineSchedule, Pipeline)
            .join(Pipeline, Pipeline.id == PipelineSchedule.pipeline_id)
            .filter(
                PipelineSchedule.enabled == True,
                PipelineSchedule.next_run_at <= now,
                PipelineSchedule.cron.isnot(None),
                Pipeline.enabled == True,
            )
            .all()
        )
        for sched, pipeline in due_schedules:
            try:
                if pipeline.owner_scope_kind == "org":
                    if not flag_enabled(pipeline.owner_scope_id, "new_pipelines"):
                        continue
                run_pipeline_task.delay(pipeline.id, "cron", None, schedule_id=sched.id)
                dispatched += 1
                sched.next_run_at = compute_next_run(
                    sched.cron, sched.timezone or "UTC", now_utc=now,
                )
            except Exception as exc:
                logger.error("dispatch_pipelines: failed for schedule %s: %s", sched.id, exc)

        # `dispatched` counts what we enqueued; `backlog` what nobody has picked
        # up yet. A backlog that only ever grows means no worker is consuming the
        # `pipelines` queue — the failure mode this task cannot otherwise detect,
        # since .delay() succeeds whether or not a consumer exists.
        backlog = _queue_depth("pipelines")
        if dispatched or (isinstance(backlog, int) and backlog):
            logger.info(
                "dispatch_pipelines: dispatched=%d backlog=%s", dispatched, backlog
            )

        db.commit()

    except Exception:
        logger.exception("dispatch_pipelines failed")
        db.rollback()
    finally:
        db.close()


@shared_task(name="run_pipeline_task", time_limit=3600)
def run_pipeline_task(
    pipeline_id: str,
    triggered_by: str,
    triggered_by_user_id: str | None,
    backfill_since: str | None = None,
    schedule_id: str | None = None,
):
    """Execute a single pipeline run. Delegates to runner.run_pipeline().

    `backfill_since` (ISO-8601 datetime string; Celery args must be JSON-safe)
    → "Load history" / bootstrap run: overrides the dlt incremental cursor for
    this run only, does not advance the schedule.
    `schedule_id` → new-model run: extracts only that schedule's table subset.
    """
    from backend.pipelines.runner import run_pipeline
    run_id = run_pipeline(
        pipeline_id, triggered_by, triggered_by_user_id,
        backfill_since=backfill_since, schedule_id=schedule_id,
    )
    if run_id:
        logger.info("Pipeline %s run completed: run_id=%s", pipeline_id, run_id)
    return run_id


@shared_task(name="first_ingest_task", time_limit=3600)
def first_ingest_task(connection_id: int, triggered_by_user_id: str | None):
    """Bootstrap ingest: run every pipeline freshly materialised for `connection_id`.

    Fired from `api/connections.create_connection` immediately after
    `materialize_templates_for_connection` succeeds. Pulls
    `now - settings.first_ingest_lookback_days` forward for incremental tables
    when that setting is > 0; at 0 (or below) there is no lower bound and the
    first run loads all history up to T-1. Full-snapshot tables ignore it
    either way and load everything.

    Runs sequentially (one pipeline per loop iter) so multiple tables on the
    same connection don't fan out a herd of concurrent dlt processes against
    the same source DB.
    """
    from backend.config import settings
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline
    from backend.pipelines.runner import run_pipeline

    db = SessionLocal()
    try:
        pipelines = (
            db.query(Pipeline)
            .filter(Pipeline.source_connection_id == connection_id)
            .all()
        )
        if not pipelines:
            logger.info("first_ingest_task: no pipelines for connection %s", connection_id)
            return 0

        # N > 0 → pull `[now − N days, T-1)`. N ≤ 0 → no lower bound; dlt's
        # sentinel pulls all history (same convention as
        # `template_materializer._apply_mysql_t1_schedule` / `watermark_tasks`).
        lookback_days = int(getattr(settings, "first_ingest_lookback_days", 0) or 0)
        backfill_since_iso = (
            (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
            if lookback_days > 0 else None
        )
        ran = 0
        for p in pipelines:
            if p.first_ingest_done:
                continue
            try:
                schedules = list(getattr(p, "schedules", []) or [])
                if schedules:
                    # New model: seed each schedule's table subset.
                    for s in schedules:
                        run_pipeline(
                            p.id, "bootstrap", triggered_by_user_id,
                            backfill_since=backfill_since_iso, schedule_id=s.id,
                        )
                else:
                    run_pipeline(
                        p.id, "bootstrap", triggered_by_user_id,
                        # Full-snapshot tables ignore this; incremental ones use it
                        # as the dlt `initial_value` for their cursor.
                        backfill_since=backfill_since_iso,
                    )
                ran += 1
            except Exception:
                logger.exception("first_ingest_task: pipeline %s failed", p.id)
        logger.info("first_ingest_task: ran %d pipeline(s) for connection %s", ran, connection_id)
        return ran
    finally:
        db.close()


@shared_task(name="pipeline_health_check")
def pipeline_health_check():
    """
    Health check for all enabled pipelines.

    For each enabled pipeline:
    - Check if the HEAD Parquet table exists on the DataPlane
    - Check if the pipeline is stale (last_run_at > 2× cron_interval ago)
    - If unhealthy (missing OR stale): update pipeline.last_run_status = "stale"
      and set connection.health_status = "unhealthy"

    Runs every 300 seconds via beat schedule.
    """
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline
    from backend.models.database_connection import DatabaseConnection
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane
    from croniter import croniter

    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        pipelines = db.query(Pipeline).filter(Pipeline.enabled == True).all()
        unhealthy_count = 0

        for pipeline in pipelines:
            try:
                # Determine scope for this pipeline
                scope = OwnerScope(pipeline.owner_scope_kind, pipeline.owner_scope_id)
                plane = get_default_plane(scope, db)

                # Check if target table exists — but only meaningful after the
                # bootstrap has actually landed a row. A pre-bootstrap pipeline
                # (or one whose only successful runs returned zero rows) has no
                # BQ table yet by design; flagging it stale would be a false
                # positive and noisy.
                if pipeline.first_ingest_done:
                    table_missing = not plane.table_exists(scope, pipeline.target_table)
                else:
                    table_missing = False

                # Check staleness: last_run_at > 2× cron_interval?
                is_stale = False
                if pipeline.cron and pipeline.last_run_at:
                    try:
                        # `pipeline.last_run_at` is naive (Column(DateTime) stores
                        # UTC without tzinfo). `now` and croniter outputs derived
                        # from it are aware. Coerce before subtracting to avoid
                        # TypeError: can't subtract offset-naive and offset-aware.
                        last_run = pipeline.last_run_at
                        if last_run.tzinfo is None:
                            last_run = last_run.replace(tzinfo=timezone.utc)
                        cron = croniter(pipeline.cron, now)
                        next_run = cron.get_next(datetime)
                        interval = (next_run - now).total_seconds()
                        time_since_last_run = (now - last_run).total_seconds()
                        is_stale = time_since_last_run > (2 * interval)
                    except Exception as e:
                        logger.warning(
                            "pipeline_health_check: failed to check staleness for pipeline %s: %s",
                            pipeline.id, e
                        )
                        is_stale = False

                # Determine health
                is_unhealthy = table_missing or is_stale

                if is_unhealthy:
                    # Update pipeline status
                    pipeline.last_run_status = "stale"

                    # Update connection health
                    connection = db.query(DatabaseConnection).filter(
                        DatabaseConnection.id == pipeline.source_connection_id
                    ).first()
                    if connection:
                        connection.health_status = "unhealthy"

                    unhealthy_count += 1

            except Exception as e:
                logger.error("pipeline_health_check: failed for pipeline %s: %s", pipeline.id, e)

        if unhealthy_count:
            logger.info("pipeline_health_check: marked %d pipeline(s) as unhealthy", unhealthy_count)

        db.commit()

    except Exception:
        logger.exception("pipeline_health_check failed")
        db.rollback()
    finally:
        db.close()
