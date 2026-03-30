"""Dashboard SQLite cache service.

Materializes all SQL-backed widgets from a dashboard into a single SQLite
file, uploads it to DO Spaces, and serves reads from a local cache with
1-hour TTL (same pattern as DatasetSQLiteConnector.from_connection()).
"""

import logging
import os
import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

CACHE_DIR = "/tmp/gruda_dashboard_cache"
CACHE_TTL_SECONDS = 3600  # 1 hour


@dataclass
class MaterializeResult:
    """Result of a dashboard materialization."""
    do_key: str
    widgets_total: int
    widgets_succeeded: int
    widgets_failed: int
    widget_errors: dict


def _sanitize_widget_id(widget_id: str) -> str:
    """Convert a widget ID to a safe SQLite table name."""
    name = re.sub(r"[^a-z0-9_]", "_", widget_id.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    if not name or name[0].isdigit():
        name = f"w_{name}"
    return name[:60]


def _sqlite_type_for_value(value) -> str:
    """Infer SQLite column type from a Python value."""
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"


def _infer_column_types(columns: list[str], rows: list[tuple]) -> list[str]:
    """Infer SQLite types from the first non-null values in each column."""
    types = ["TEXT"] * len(columns)
    for row in rows:
        all_resolved = True
        for i, val in enumerate(row):
            if types[i] != "TEXT":
                continue
            if val is not None:
                types[i] = _sqlite_type_for_value(val)
            else:
                all_resolved = False
        if all_resolved:
            break
    return types


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


def _apply_date_filter(sql: str, date_col: str, days: int) -> str:
    """Wrap SQL in a subquery with a date range filter."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    return f'SELECT * FROM ({sql}) AS _date_scoped WHERE "{date_col}" >= \'{cutoff}\''


def materialize_dashboard(dashboard_id: int) -> MaterializeResult:
    """Execute all widget SQLs against source DB, build SQLite, upload to DO Spaces.

    Features:
    - Connection sharing: widgets grouped by connectionId, one connector per group
    - Date range scoping: appends date filter using trendDateColumn or data_context
    - Error isolation: partial success -> 'ready', all fail -> 'failed'

    Returns a MaterializeResult with the DO key and widget statistics.
    """
    from backend.config import settings
    from backend.connectors.factory import get_connector_for_connection, get_connector_registration
    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard
    from backend.models.database_connection import DatabaseConnection
    from backend.services import object_storage

    db = SessionLocal()
    try:
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard:
            raise ValueError(f"Dashboard {dashboard_id} not found")

        dashboard.cache_status = "building"
        db.commit()

        widgets = dashboard.widgets or []
        data_context = dashboard.data_context
        date_range_days = dashboard.cache_date_range_days or 90

        # Group SQL-backed widgets by connectionId for connection sharing
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

        # Create temp SQLite file
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        sqlite_path = tmp.name

        conn = sqlite3.connect(sqlite_path)
        try:
            # Create metadata table
            conn.execute(
                "CREATE TABLE _meta ("
                "  widget_id TEXT PRIMARY KEY,"
                "  table_name TEXT NOT NULL,"
                "  original_sql TEXT,"
                "  materialized_at TEXT NOT NULL,"
                "  row_count INTEGER NOT NULL DEFAULT 0,"
                "  error TEXT"
                ")"
            )
            conn.commit()

            # Process each connection group (one connector per connectionId)
            for connection_id, group_widgets in connection_groups.items():
                connection = db.query(DatabaseConnection).filter(
                    DatabaseConnection.id == connection_id,
                    DatabaseConnection.user_id == dashboard.user_id,
                ).first()

                if not connection:
                    for widget in group_widgets:
                        w_id = widget["id"]
                        table_name = _sanitize_widget_id(w_id)
                        materialized_at = datetime.utcnow().isoformat()
                        error_msg = f"Connection {connection_id} not found"
                        conn.execute(
                            "INSERT INTO _meta (widget_id, table_name, original_sql, materialized_at, row_count, error) "
                            "VALUES (?, ?, ?, ?, 0, ?)",
                            (w_id, table_name, widget.get("dataSource", {}).get("sql"), materialized_at, error_msg),
                        )
                        widgets_failed += 1
                        widget_errors[w_id] = error_msg
                    conn.commit()
                    continue

                # Skip connectors that don't support server-side queries (e.g. dataset/SQLite)
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
                        table_name = _sanitize_widget_id(w_id)
                        materialized_at = datetime.utcnow().isoformat()

                        try:
                            # Apply date range filter if applicable
                            query_sql = original_sql
                            date_col = _get_date_column(widget, data_context)
                            if date_col:
                                query_sql = _apply_date_filter(original_sql, date_col, date_range_days)

                            result = connector.execute_query(query_sql)

                            # Create table with inferred types
                            col_types = _infer_column_types(result.columns, result.rows)
                            col_defs = ", ".join(
                                f'"{col}" {ctype}' for col, ctype in zip(result.columns, col_types)
                            )
                            conn.execute(f'CREATE TABLE "{table_name}" ({col_defs})')

                            # Insert rows
                            if result.rows:
                                placeholders = ", ".join(["?"] * len(result.columns))
                                conn.executemany(
                                    f'INSERT INTO "{table_name}" VALUES ({placeholders})',
                                    result.rows,
                                )

                            conn.execute(
                                "INSERT INTO _meta (widget_id, table_name, original_sql, materialized_at, row_count, error) "
                                "VALUES (?, ?, ?, ?, ?, NULL)",
                                (w_id, table_name, original_sql, materialized_at, result.row_count),
                            )
                            conn.commit()

                            widgets_succeeded += 1
                            logger.info(
                                "Materialized widget %s (%s) with %d rows",
                                w_id, table_name, result.row_count,
                            )

                        except Exception as widget_err:
                            logger.error("Failed to materialize widget %s: %s", w_id, widget_err)
                            conn.execute(
                                "INSERT OR REPLACE INTO _meta (widget_id, table_name, original_sql, materialized_at, row_count, error) "
                                "VALUES (?, ?, ?, ?, 0, ?)",
                                (w_id, table_name, original_sql, materialized_at, str(widget_err)),
                            )
                            conn.commit()
                            widgets_failed += 1
                            widget_errors[w_id] = str(widget_err)
                finally:
                    connector.close()

        finally:
            conn.close()

        # Upload to DO Spaces
        do_key = f"{settings.do_spaces_base_path}/{dashboard.user_id}/dashboards/{dashboard_id}.sqlite"
        with open(sqlite_path, "rb") as f:
            object_storage.upload_bytes(do_key, f.read(), content_type="application/x-sqlite3")

        # Atomic write to local cache
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(CACHE_DIR, f"{dashboard_id}.sqlite")
        os.rename(sqlite_path, cache_path)

        # Error isolation: 'ready' if any widget succeeded, 'failed' only if all failed
        if widgets_total == 0:
            status = "ready"
        elif widgets_succeeded > 0:
            status = "ready"
        else:
            status = "failed"

        # Update dashboard record
        dashboard.cache_key = do_key
        dashboard.cache_built_at = datetime.utcnow()
        dashboard.cache_status = status
        db.commit()

        logger.info("Dashboard %d cache materialized to %s", dashboard_id, do_key)
        return MaterializeResult(
            do_key=do_key,
            widgets_total=widgets_total,
            widgets_succeeded=widgets_succeeded,
            widgets_failed=widgets_failed,
            widget_errors=widget_errors,
        )

    except Exception:
        # Mark as failed and re-raise
        try:
            dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
            if dashboard:
                dashboard.cache_status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()


def get_cache_path(dashboard_id: int) -> str:
    """Download/return local cached SQLite path.

    Uses local cache with 1-hour TTL. Downloads from DO Spaces if
    missing or stale, using atomic write (temp file + rename).

    Returns the local file path to the cached SQLite.
    """
    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard
    from backend.services import object_storage

    cache_path = os.path.join(CACHE_DIR, f"{dashboard_id}.sqlite")

    cache_valid = (
        os.path.exists(cache_path)
        and os.path.getmtime(cache_path) > time.time() - CACHE_TTL_SECONDS
    )

    if cache_valid:
        return cache_path

    # Need to download from DO Spaces
    db = SessionLocal()
    try:
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if not dashboard or not dashboard.cache_key:
            raise FileNotFoundError(f"No cache available for dashboard {dashboard_id}")

        data = object_storage.download_bytes(dashboard.cache_key)
        if data is None:
            raise FileNotFoundError(
                f"SQLite file not found in DO Spaces: {dashboard.cache_key}"
            )

        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp_path = cache_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.rename(tmp_path, cache_path)

        return cache_path
    finally:
        db.close()


def read_widget_data(cache_path: str, widget_id: str) -> dict:
    """Read a single widget's data from the SQLite cache.

    Returns a dict with keys: columns, rows, row_count.
    """
    table_name = _sanitize_widget_id(widget_id)

    uri = f"file:{cache_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        # Check if table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            raise ValueError(f"Widget table '{table_name}' not found in cache")

        cursor = conn.execute(f'SELECT * FROM "{table_name}"')
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    finally:
        conn.close()


def delete_cache(dashboard_id: int) -> None:
    """Delete cache from DO Spaces and local filesystem."""
    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard
    from backend.services import object_storage

    db = SessionLocal()
    try:
        dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        if dashboard and dashboard.cache_key:
            object_storage.delete_object(dashboard.cache_key)
            dashboard.cache_key = None
            dashboard.cache_built_at = None
            dashboard.cache_status = None
            db.commit()
    finally:
        db.close()

    # Remove local cache file
    cache_path = os.path.join(CACHE_DIR, f"{dashboard_id}.sqlite")
    try:
        os.remove(cache_path)
    except FileNotFoundError:
        pass
