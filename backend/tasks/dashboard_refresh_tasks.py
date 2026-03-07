"""Celery tasks for scheduled dashboard widget refresh."""

import logging
from datetime import datetime, timezone

from celery import shared_task
from backend.database.session import SessionLocal
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun

logger = logging.getLogger(__name__)


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

        for dashboard in due_dashboards:
            try:
                execute_dashboard_refresh.delay(dashboard.id)
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
    Execute a single dashboard refresh: re-run all SQL-backed widgets,
    persist updated data to dashboard.widgets, and record the run.

    Args:
        dashboard_id: The ID of the Dashboard to refresh.
    """
    from sqlalchemy.orm.attributes import flag_modified
    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector
    from backend.services.widget_transform import transform_widget_data

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

        widgets = dashboard.widgets or []
        widgets_total = 0
        widgets_succeeded = 0
        widgets_failed = 0
        widget_errors: dict = {}

        updated_widgets = []
        for widget in widgets:
            data_source = widget.get("dataSource")
            if not data_source:
                updated_widgets.append(widget)
                continue

            widget_id = widget.get("id", "unknown")
            connection_id = data_source.get("connectionId")
            sql = data_source.get("sql")
            mapping = data_source.get("mapping")

            if not connection_id or not sql or not mapping:
                updated_widgets.append(widget)
                continue

            widgets_total += 1

            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == dashboard.user_id,
            ).first()

            if not connection:
                widgets_failed += 1
                widget_errors[widget_id] = f"Connection {connection_id} not found"
                updated_widgets.append(widget)
                continue

            connector = get_connector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                database=connection.database,
                username=connection.username,
                password=connection.password,
                ssl_enabled=connection.ssl_enabled,
                ssl_ca_cert=connection.ssl_ca_cert,
            )

            try:
                result = connector.execute_query(sql)
                config = transform_widget_data(result, mapping)

                # Merge updated config into widget
                updated_widget = dict(widget)
                widget_inner = dict(updated_widget.get("widget", {}))
                widget_inner["config"] = {**widget_inner.get("config", {}), **config}
                updated_widget["widget"] = widget_inner

                # Update lastRefreshedAt on dataSource
                updated_ds = dict(data_source)
                updated_ds["lastRefreshedAt"] = datetime.now(timezone.utc).isoformat()
                updated_widget["dataSource"] = updated_ds

                updated_widgets.append(updated_widget)
                widgets_succeeded += 1

            except Exception as widget_err:
                logger.error(f"Widget {widget_id} refresh failed: {widget_err}")
                widgets_failed += 1
                widget_errors[widget_id] = str(widget_err)
                updated_widgets.append(widget)
            finally:
                connector.close()

        # Auto-persist updated widgets to DB
        dashboard.widgets = updated_widgets
        flag_modified(dashboard, "widgets")

        completed_at = datetime.utcnow()
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        run.status = "completed" if widgets_failed == 0 else "completed"
        run.completed_at = completed_at
        run.duration_ms = duration_ms
        run.widgets_total = widgets_total
        run.widgets_succeeded = widgets_succeeded
        run.widgets_failed = widgets_failed
        run.widget_errors = widget_errors if widget_errors else None

        db.commit()

        logger.info(
            f"Dashboard {dashboard_id} refresh complete in {duration_ms}ms: "
            f"{widgets_succeeded}/{widgets_total} widgets succeeded"
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
