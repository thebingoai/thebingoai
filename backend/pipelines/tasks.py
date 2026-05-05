"""Celery tasks for Pipeline scheduling and execution (Phase 2)."""
import logging
from datetime import datetime, timezone

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


@shared_task(name="dispatch_pipelines")
def dispatch_pipelines():
    """Beat dispatcher: runs every 60s, fires run_pipeline for due pipelines.

    Gated by the new_pipelines feature flag per Org.
    """
    from croniter import croniter
    from sqlalchemy import text
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline
    from backend.config.feature_flags import enabled as flag_enabled

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

                # Advance next_run_at
                pipeline.next_run_at = croniter(pipeline.cron, now).get_next(datetime)

            except Exception as exc:
                logger.error("dispatch_pipelines: failed for pipeline %s: %s", pipeline.id, exc)

        if dispatched:
            logger.info("dispatch_pipelines: dispatched %d pipeline run(s)", dispatched)

        db.commit()

    except Exception:
        logger.exception("dispatch_pipelines failed")
        db.rollback()
    finally:
        db.close()


@shared_task(name="run_pipeline_task", time_limit=1800)
def run_pipeline_task(pipeline_id: str, triggered_by: str, triggered_by_user_id: str | None):
    """Execute a single pipeline run. Delegates to runner.run_pipeline()."""
    from backend.pipelines.runner import run_pipeline
    run_id = run_pipeline(pipeline_id, triggered_by, triggered_by_user_id)
    if run_id:
        logger.info("Pipeline %s run completed: run_id=%s", pipeline_id, run_id)
    return run_id


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

                # Check if target table exists
                table_exists = plane.table_exists(scope, pipeline.target_table)

                # Check staleness: last_run_at > 2× cron_interval?
                is_stale = False
                if pipeline.cron and pipeline.last_run_at:
                    try:
                        # Get next run time from current cron expression
                        cron = croniter(pipeline.cron, now)
                        last_expected_run = cron.get_prev(datetime)
                        # If last_run_at is before last_expected_run - 1× interval, it's stale
                        # Simple heuristic: if last_run_at is > 2× the interval old, mark stale
                        next_run = cron.get_next(datetime)
                        interval = (next_run - now).total_seconds()
                        time_since_last_run = (now - pipeline.last_run_at).total_seconds()
                        is_stale = time_since_last_run > (2 * interval)
                    except Exception as e:
                        logger.warning(
                            "pipeline_health_check: failed to check staleness for pipeline %s: %s",
                            pipeline.id, e
                        )
                        is_stale = False

                # Determine health
                is_unhealthy = (not table_exists) or is_stale

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
