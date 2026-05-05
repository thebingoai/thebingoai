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
