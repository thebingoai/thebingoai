"""Celery tasks for scheduled dashboard widget refresh."""

import logging
import random
from datetime import datetime

from celery import shared_task
from backend.database.session import SessionLocal
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun

logger = logging.getLogger(__name__)

# Max stagger delay per dashboard (seconds) to avoid thundering herd
STAGGER_MAX_SECONDS = 60


@shared_task(name="dispatch_dashboard_refreshes")
def dispatch_dashboard_refreshes():
    """
    Dispatcher task that runs every 60 seconds via Celery Beat.

    Queries all active dashboard schedules whose next_run_at is due and
    dispatches execute_dashboard_refresh for each, then advances next_run_at.
    """
    from backend.tasks.cron_dispatcher import dispatch_due_rows

    db = SessionLocal()
    now = datetime.utcnow()

    def _dispatch_dashboard(dashboard):
        countdown = random.uniform(0, STAGGER_MAX_SECONDS)
        execute_dashboard_refresh.apply_async(
            args=[dashboard.id], countdown=countdown,
        )
        dashboard.last_run_at = now

    try:
        count = dispatch_due_rows(
            db,
            model_cls=Dashboard,
            enabled_field="schedule_active",
            cron_field="cron_expression",
            next_run_field="next_run_at",
            dispatch_fn=_dispatch_dashboard,
            now=now,
        )
        if count:
            logger.info("Dispatched refresh for %d due dashboard(s)", count)
        db.commit()
    except Exception as e:
        logger.error("dispatch_dashboard_refreshes failed: %s", e)
        db.rollback()
    finally:
        db.close()


@shared_task(name="execute_dashboard_refresh", time_limit=300)
def execute_dashboard_refresh(dashboard_id: int):
    """
    Execute a single dashboard refresh by materializing all SQL-backed
    widgets into a SQLite cache via dashboard_cache.materialize_dashboard().

    Records a DashboardRefreshRun with widget statistics.
    """
    from backend.services.dashboard_cache import materialize_dashboard

    db = SessionLocal()
    run = None
    started_at = datetime.utcnow()

    try:
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard:
            logger.warning(f"Dashboard {dashboard_id} not found for refresh")
            return

        # Create a run record
        run = DashboardRefreshRun(
            dashboard_id=dashboard_id,
            status="running",
            started_at=started_at,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        logger.info(f"Executing dashboard refresh {dashboard_id} (run {run.id})")

        # Delegate to SQLite cache materialization
        result = materialize_dashboard(dashboard_id)

        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        run.status = "completed"
        run.completed_at = completed_at
        run.duration_ms = duration_ms
        run.widgets_total = result.widgets_total
        run.widgets_succeeded = result.widgets_succeeded
        run.widgets_failed = result.widgets_failed
        run.widget_errors = result.widget_errors if result.widget_errors else None

        db.commit()

        logger.info(
            f"Dashboard {dashboard_id} refresh complete in {duration_ms}ms: "
            f"{result.widgets_succeeded}/{result.widgets_total} widgets succeeded"
        )

    except Exception as e:
        logger.error(f"Dashboard {dashboard_id} refresh failed: {e}")
        if run is not None:
            try:
                completed_at = datetime.utcnow()
                run.status = "failed"
                run.error = str(e)
                run.completed_at = completed_at
                run.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()
