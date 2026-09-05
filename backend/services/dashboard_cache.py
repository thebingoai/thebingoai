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


def _sanitize_widget_id(widget_id: str | int) -> str:
    """Convert a widget ID (str or numeric) to a safe table name."""
    name = re.sub(r"[^a-z0-9_]", "_", str(widget_id).lower())
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
    duck_reader = None
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

        # Phase 2: when DuckDB-over-GCS serving is on for this Org, warm the
        # cache by computing each widget via DuckDB-over-GCS (direct httpfs)
        # instead of a per-widget BQ job. None (residency-locked / customer /
        # no-HMAC / non-GCS plane) → keep the source-connector path. Per-widget
        # fallback below handles not-yet-migrated BigQuery SQL.
        from backend.config.feature_flags import enabled as _flag_enabled
        from backend.services.data_plane_service import get_gcs_duckdb_reader, plane_table_map
        from backend.utils.sql_refs import rewrite_table_refs
        if org_id and _flag_enabled(org_id, "duckdb_widget_serving"):
            duck_reader = get_gcs_duckdb_reader(scope, db)

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

            # Source Parquet lives under the *connection's* scope (that's where
            # the Pipeline wrote it); `scope` above is the dashboard's org and
            # stays the write target for the `_dash_*` cache below.
            src_scope = OwnerScope.from_connection(connection)

            connector = get_connector_for_connection(connection, db)
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

                        # Rewrite source table names (e.g. `orders`) → the
                        # Pipeline's materialized plane table (e.g. `acme__orders`)
                        # so the DuckDB-over-GCS warm below resolves the Parquet.
                        from backend.utils.sql_refs import qualifier_allowlist
                        query_sql, _ = rewrite_table_refs(
                            original_sql, plane_table_map(connection, db),
                            qualifier_allowlist(connection),
                        )
                        date_col = _get_date_column(widget, data_context)
                        if date_col:
                            query_sql = _apply_date_filter(query_sql, date_col, date_range_days)

                        result = None
                        if duck_reader is not None:
                            try:
                                result = duck_reader.query(src_scope, query_sql)
                            except Exception as duck_err:
                                logger.warning(
                                    "DuckDB warm failed for widget %s, using source connector: %s",
                                    w_id, duck_err,
                                )
                        if result is None:
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

        # Invalidate the Redis widget result cache: keys embed this generation,
        # so the next read misses and repopulates from the fresh `_dash_*` data.
        if widgets_succeeded:
            from backend.services.widget_result_cache import bump_generation
            bump_generation(dashboard_id)

        return MaterializeResult(
            widgets_total=widgets_total,
            widgets_succeeded=widgets_succeeded,
            widgets_failed=widgets_failed,
            widget_errors=widget_errors,
        )
    finally:
        if duck_reader is not None:
            duck_reader.close()
        db.close()


def enqueue_dashboard_warm_for_table(scope, table_name: str) -> int:
    """Enqueue a cache warm for each dashboard backed by *table_name* (GAP-2f).

    Called after a pipeline/dbt write so dashboards reading that table refresh
    promptly instead of waiting for the periodic dispatcher. Debounced via the
    same `materialize_rate:{id}` Redis key `/materialize` uses (5 min) so a busy
    writer can't trigger warm storms. Best-effort — never raises into the caller.
    Returns the number of dashboards enqueued.
    """
    try:
        import redis as _redis

        from backend.config import settings
        from backend.database.session import SessionLocal
        from backend.models.dashboard import Dashboard
        from backend.models.user import User
        from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
        from backend.utils.sql_refs import extract_table_refs

        tnorm = table_name.lower()
        enqueued = 0
        with SessionLocal() as db:
            if scope.kind == "org":
                user_ids = [u.id for u in db.query(User).filter(User.org_id == scope.id).all()]
                dashboards = (
                    db.query(Dashboard).filter(Dashboard.user_id.in_(user_ids)).all()
                    if user_ids else []
                )
            else:
                dashboards = db.query(Dashboard).filter(Dashboard.user_id == scope.id).all()

            r = _redis.from_url(settings.redis_url)
            try:
                for dash in dashboards:
                    backed = any(
                        tnorm in extract_table_refs((w.get("dataSource") or {}).get("sql") or "")
                        for w in (dash.widgets or [])
                    )
                    if not backed:
                        continue
                    key = f"materialize_rate:{dash.id}"
                    if r.exists(key):
                        continue  # debounce — recently warmed / queued
                    r.setex(key, 300, "1")
                    execute_dashboard_refresh.delay(dash.id)
                    enqueued += 1
            finally:
                r.close()
        if enqueued:
            logger.info("Enqueued warm for %d dashboard(s) backed by %s", enqueued, table_name)
        return enqueued
    except Exception:
        logger.warning("enqueue_dashboard_warm_for_table failed for %s", table_name, exc_info=True)
        return 0


def widget_plane_scope(org_id: str | None, user_id: str):
    """OwnerScope the `_dash_*` widget cache lives under: the Org when there is one,
    else the user.

    Callers that pre-resolve the plane (see `read_widget_data_plane`'s `plane` arg)
    must derive the scope through here — resolving a different scope than the read
    would hand back a plane pointing at another tenant's bucket.
    """
    from backend.data_plane.scope import OwnerScope

    return OwnerScope("org", org_id) if org_id else OwnerScope("user", user_id)


#: `plane` not supplied at all, as distinct from "supplied, and there is none".
#: A plain None default cannot tell those apart, and conflating them is a bug:
#: a caller whose own resolution failed would have every widget re-resolve here,
#: restoring the per-widget session this argument exists to remove — and under
#: lockdown re-running provision-on-miss once per widget with it.
_UNSET = object()


def read_widget_data_plane(
    dashboard_id: int,
    widget_id: str,
    org_id: str | None,
    user_id: str,
    plane=_UNSET,
) -> dict | None:
    """Read widget data from DataPlane. Returns None when no Parquet cache exists yet.

    `plane` lets a caller reading many widgets resolve once and pass the result in.
    Resolving here calls `get_default_plane` with no session, which opens its own
    (`data_plane_service.get_default_plane` defaults `db=None`) — so a per-widget call
    takes a second pooled connection while the caller's request session is still
    checked out. A 15-widget dashboard did that 15 times against a 10-connection pool.
    Omitted entirely, the historical self-resolving behaviour is unchanged; passed
    as None it means the caller resolved and got nothing, so the cache is cold.
    """
    scope = widget_plane_scope(org_id, user_id)
    if plane is _UNSET:
        from backend.services.data_plane_service import get_default_plane
        plane = get_default_plane(scope)
    if plane is None:
        return None
    table_name = f"_dash_{dashboard_id}__{_sanitize_widget_id(widget_id)}"

    # read_table, not table_exists + query. The exact table name is already
    # known, and on BigQuery those two calls cost two live metadata round-trips
    # before the job starts — a get_table, then a fully paginated tables.list
    # inside _rewrite_sql. At ~200-600ms each across a 20-widget dashboard that
    # was seconds of open latency, all of it holding the request's pool slot.
    result = plane.read_table(scope, table_name)
    if result is None:
        return None

    from backend.config import settings

    return {
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        # The bake wrote whatever the engine returned, and the engine caps at
        # max_query_rows — so a cache holding exactly the cap is the prefix of a
        # bigger result, and a client-side KPI sum over it is wrong. The row
        # count is the only trace left: `truncated` was never stored, and the
        # cloud plane's drop_table is a no-op, so tables baked before this fix
        # cannot be evicted either.
        # ponytail: a genuine cap-sized result reads as truncated; persist a
        # meta row alongside the Parquet if that false positive ever bites.
        "truncated": bool(getattr(result, "truncated", False))
        or result.row_count >= settings.max_query_rows,
    }
