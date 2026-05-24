"""Dashboard cache service.

Materializes SQL-backed widgets from a dashboard into Parquet on the Org's
DataPlane. The legacy SQLite-on-DO-Spaces path was removed; this module is
DataPlane-only.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class MaterializeResult:
    """Result of a dashboard materialization."""
    widgets_total: int
    widgets_succeeded: int
    widgets_failed: int
    widget_errors: dict


def _sanitize_widget_id(widget_id: str) -> str:
    """Convert a widget ID to a safe table name."""
    name = re.sub(r"[^a-z0-9_]", "_", widget_id.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = f"w_{name}"
    return name[:60]


def _get_date_column(widget: dict, data_context: dict | None) -> str | None:
    """Find the date column for date range scoping.

    Priority: widget mapping's trendDateColumn > data_context date dimensions.
    """
    data_source = widget.get("dataSource", {})
    mapping = data_source.get("mapping", {})
    date_col = mapping.get("trendDateColumn")
    if date_col:
        return date_col

    if data_context:
        dimensions = data_context.get("dimensions", {})
        for dim_data in dimensions.values():
            if dim_data.get("type") == "date":
                return dim_data.get("column")

    return None


def _is_pipeline_output_widget(sql: str, org_id: str, db) -> bool:
    """Return True if *sql* is a simple SELECT from a Pipeline-output table in this Org."""
    from backend.models.pipeline import Pipeline
    m = re.search(r'\bFROM\s+["`]?(\w+)["`]?\b', sql, re.IGNORECASE)
    if not m:
        return False
    table_name = m.group(1).lower()
    exists = db.query(Pipeline).filter(
        Pipeline.target_table == table_name,
        Pipeline.owner_scope_id == org_id,
    ).first()
    return exists is not None


def _apply_date_filter(sql: str, date_col: str, days: int) -> str:
    """Wrap SQL in a subquery with a date range filter."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    return f'SELECT * FROM ({sql}) AS _date_scoped WHERE "{date_col}" >= \'{cutoff}\''


def _get_org_for_user(user_id: str) -> str | None:
    """Return the org_id for *user_id* (None if not in an org)."""
    try:
        from backend.database.session import SessionLocal
        from backend.models.user import User
        with SessionLocal() as db:
            user = db.query(User).filter(User.id == user_id).first()
            return getattr(user, "org_id", None) if user else None
    except Exception:
        return None


def materialize_dashboard(dashboard_id: int) -> MaterializeResult:
    """Materialize all SQL-backed widgets for a dashboard to the Org's DataPlane."""
    import pyarrow as pa

    from backend.connectors.factory import get_connector_for_connection, get_connector_registration
    from backend.data_plane.scope import OwnerScope
    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard
    from backend.models.database_connection import DatabaseConnection
    from backend.services.data_plane_service import get_default_plane

    db = SessionLocal()
    try:
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")

        widgets = dashboard.widgets or []
        data_context = dashboard.data_context
        date_range_days = dashboard.cache_date_range_days or 90

        org_id = _get_org_for_user(dashboard.user_id)
        scope = OwnerScope("org", org_id) if org_id else OwnerScope("user", dashboard.user_id)
        plane = get_default_plane(scope)

        connection_groups: dict[int, list[dict]] = {}
        for widget in widgets:
            data_source = widget.get("dataSource")
            if not data_source:
                continue
            widget_id = widget.get("id")
            connection_id = data_source.get("connectionId")
            sql = data_source.get("sql")
            if not widget_id or not connection_id or not sql:
                continue
            connection_groups.setdefault(connection_id, []).append(widget)

        widgets_total = sum(len(wl) for wl in connection_groups.values())
        widgets_succeeded = 0
        widgets_failed = 0
        widget_errors: dict[str, str] = {}

        for connection_id, group_widgets in connection_groups.items():
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == dashboard.user_id,
            ).first()

            if not connection:
                for widget in group_widgets:
                    w_id = widget["id"]
                    error_msg = f"Connection {connection_id} not found"
                    widget_errors[w_id] = error_msg
                    widgets_failed += 1
                continue

            reg = get_connector_registration(connection.db_type)
            if reg and reg.skip_schema_refresh:
                widgets_total -= len(group_widgets)
                continue

            connector = get_connector_for_connection(connection)
            try:
                for widget in group_widgets:
                    w_id = widget["id"]
                    data_source = widget["dataSource"]
                    original_sql = data_source["sql"]
                    table_name = f"_dash_{dashboard_id}__{_sanitize_widget_id(w_id)}"

                    try:
                        if _is_pipeline_output_widget(original_sql, org_id or dashboard.user_id, db):
                            logger.debug("Skipping materialization for pipeline-backed widget %s", w_id)
                            widgets_total -= 1
                            continue

                        query_sql = original_sql
                        date_col = _get_date_column(widget, data_context)
                        if date_col:
                            query_sql = _apply_date_filter(original_sql, date_col, date_range_days)

                        # Route `bigquery_ga4` widget SQL through the data
                        # plane so bare table names resolve to the
                        # materialised view. Source connector's BQ client
                        # cannot see the data plane's project.
                        if connection.db_type == "bigquery_ga4":
                            from backend.data_plane.scope import OwnerScope as _OS
                            from backend.models.pipeline import Pipeline as _Pipeline
                            from backend.services.data_plane_service import (
                                get_default_plane as _get_default_plane,
                            )
                            _p = db.query(_Pipeline).filter(
                                _Pipeline.source_connection_id == connection.id,
                            ).first()
                            if _p is not None:
                                _s = _OS(kind=_p.owner_scope_kind, id=_p.owner_scope_id)
                                _plane = _get_default_plane(_s, db)
                                result = _plane.query(_s, query_sql)
                            else:
                                result = connector.execute_query(query_sql)
                        else:
                            result = connector.execute_query(query_sql)

                        arrow_table = pa.table(
                            {col: [row[i] for row in result.rows] for i, col in enumerate(result.columns)}
                        )
                        plane.write_parquet(scope, table_name, arrow_table)

                        widgets_succeeded += 1
                        logger.info("Materialized widget %s → DataPlane table %s (%d rows)", w_id, table_name, result.row_count)
                    except Exception as widget_err:
                        logger.error("Failed to materialize widget %s: %s", w_id, widget_err)
                        widget_errors[w_id] = str(widget_err)
                        widgets_failed += 1
            finally:
                connector.close()

        logger.info("Dashboard %d materialized via DataPlane", dashboard_id)
        return MaterializeResult(
            widgets_total=widgets_total,
            widgets_succeeded=widgets_succeeded,
            widgets_failed=widgets_failed,
            widget_errors=widget_errors,
        )
    finally:
        db.close()


def read_widget_data_plane(
    dashboard_id: int,
    widget_id: str,
    org_id: str | None,
    user_id: str,
) -> dict | None:
    """Read widget data from DataPlane. Returns None when no Parquet cache exists yet."""
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane

    scope = OwnerScope("org", org_id) if org_id else OwnerScope("user", user_id)
    plane = get_default_plane(scope)
    table_name = f"_dash_{dashboard_id}__{_sanitize_widget_id(widget_id)}"

    if not plane.table_exists(scope, table_name):
        return None

    result = plane.query(scope, f'SELECT * FROM "{table_name}"')
    return {
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
    }
