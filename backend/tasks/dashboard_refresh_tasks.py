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
    from croniter import croniter

    db = SessionLocal()
    now = datetime.utcnow()

    try:
        due_dashboards = (
            db.query(Dashboard)
            .filter(
                Dashboard.schedule_active == True,
                Dashboard.next_run_at <= now,
            )
            .all()
        )

        if not due_dashboards:
            return

        logger.info(f"Dispatching refresh for {len(due_dashboards)} due dashboard(s)")

        for idx, dashboard in enumerate(due_dashboards):
            try:
                # Stagger tasks to avoid thundering herd
                countdown = random.uniform(0, STAGGER_MAX_SECONDS) + idx * 2
                execute_dashboard_refresh.apply_async(
                    args=[dashboard.id], countdown=countdown,
                )
                # Advance next_run_at using croniter
                dashboard.next_run_at = croniter(dashboard.cron_expression, now).get_next(datetime)
                dashboard.last_run_at = now
            except Exception as dispatch_err:
                logger.error(f"Failed to dispatch refresh for dashboard {dashboard.id}: {dispatch_err}")

        db.commit()

    except Exception as e:
        logger.error(f"dispatch_dashboard_refreshes failed: {e}")
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
