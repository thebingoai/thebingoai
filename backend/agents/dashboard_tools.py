"""
Dashboard Tools — LangChain tool builders for dashboard creation.

Kept as a standalone module to avoid circular imports between graph.py and tool_registry.py.
"""
from typing import List, Callable
from backend.agents.context import AgentContext
from backend.agents.dashboard_layout import normalize_dashboard_layout
from backend.connectors.factory import get_connector_for_connection, get_connector_registration
import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

_VALID_WIDGET_TYPES = {"kpi", "chart", "table", "text", "filter", "pivot_table", "section"}
_DATA_WIDGET_TYPES = {"kpi", "chart", "table", "pivot_table"}
_VALID_MAPPING_TYPES = {"kpi", "chart", "table", "pivot_table"}

# sqlglot dialect per source db_type. Sibling of `widget_data._resolve_inject_dialect`
# (same lockdown rule for plane-backed types) but deliberately fail-closed: an
# unmapped type maps to "" — no rewrite at all, the pre-existing behaviour.
# Guessing wrong is free for filter injection and destructive for a rewrite.
_DB_TYPE_DIALECTS = {
    "postgresql": "postgres",
    "postgres": "postgres",
    "mysql": "mysql",
    "sqlite": "sqlite",
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "redshift": "redshift",
    "duckdb": "duckdb",
}


def _widget_sql_dialect(connection, connector) -> str:
    """Dialect of the surface `_run_widget_query` will actually execute on.

    Not always the source's: plane-backed connectors (dataset/CSV, sheets) and
    `bigquery_ga4` run through the DataPlane, and an Org on `duckdb_widget_serving`
    reads Parquet through DuckDB. Empty string when unknown → no rewrite.
    """
    if connection.db_type == "bigquery_ga4" or getattr(connector, "serves_from_plane", False) is True:
        from backend.config import settings
        return "bigquery" if settings.disable_local_data_plane else "duckdb"

    org_id = getattr(connection, "org_id", None)
    if org_id:
        from backend.config.feature_flags import enabled
        if enabled(str(org_id), "duckdb_widget_serving"):
            return "duckdb"

    return _DB_TYPE_DIALECTS.get(connection.db_type or "", "")


def _run_widget_query(connection, sql: str, db_session_factory, connector):
    """Execute widget SQL against the right surface.

    For connectors that own a managed pipeline + materialised view in the
    data plane (currently just `bigquery_ga4`), route SQL through
    `plane.query()` so bare table names like `ga4_events_17_249794534`
    resolve to the fully-qualified BigQuery view -- the source connection's
    BQ client can't see the data plane's project.

    For every other connector type, fall back to the standard
    `connector.execute_query(sql)` path.

    Runs inside asyncio.to_thread, so it creates its own session — sessions
    must not be shared across threads.
    """
    if connection.db_type == "bigquery_ga4":
        from backend.data_plane.scope import OwnerScope
        from backend.models.pipeline import Pipeline
        from backend.services.data_plane_service import get_default_plane

        db = db_session_factory()
        try:
            pipeline = db.query(Pipeline).filter(
                Pipeline.source_connection_id == connection.id,
            ).first()
            if pipeline is None:
                # No managed pipeline yet -- nothing to query. Defer to the
                # source connector so the LLM sees a clear "table not found"
                # rather than a silent empty result.
                return connector.execute_query(sql)
            scope = OwnerScope(kind=pipeline.owner_scope_kind, id=pipeline.owner_scope_id)
            plane = get_default_plane(scope, db)
            return plane.query(scope, sql)
        finally:
            db.close()

    plane_result = _run_widget_query_on_plane(connection, sql, db_session_factory)
    if plane_result is not None:
        return plane_result
    return connector.execute_query(sql)


def _run_widget_query_on_plane(connection, sql: str, db_session_factory):
    """Run generation-time widget SQL over the DataPlane Parquet, or None.

    Mirrors `api/widget_data._serve_widget_via_dataplane`: once the Org has
    `duckdb_widget_serving` on, the agent emits DuckDB SQL (see
    `agents/profile_defaults._dialect_hints_for_target`), so running it against
    the live source connector would fail on DuckDB-only constructs. Rewrite the
    source table refs to their plane targets and read the lake instead.

    No transpile — stored SQL is assumed DuckDB, same contract as the serve
    path. Returns None on any miss so the caller falls back to the source.
    """
    org_id = getattr(connection, "org_id", None)
    if not org_id:
        return None

    from backend.config.feature_flags import enabled
    if not enabled(str(org_id), "duckdb_widget_serving"):
        return None

    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
    from backend.services.data_plane_service import (
        get_gcs_duckdb_reader,
        get_plane_for_connection,
        plane_table_map,
    )
    from backend.utils.sql_refs import qualifier_allowlist, rewrite_table_refs

    db = db_session_factory()
    reader = None
    try:
        table_map = plane_table_map(connection, db)
        if not table_map:
            return None  # no pipelines → nothing materialized → source
        plane, scope = get_plane_for_connection(connection, db)
        plane_sql, _ = rewrite_table_refs(sql, table_map, qualifier_allowlist(connection))

        if isinstance(plane, LocalFilesystemDataPlane):
            return plane.query(scope, plane_sql)

        reader = get_gcs_duckdb_reader(scope, db)
        if reader is None:
            return None  # residency-locked / customer / no-HMAC → source
        return reader.query(scope, plane_sql)
    except Exception as e:
        logger.warning(
            "Plane read failed for generation-time widget SQL on connection %s, "
            "using source connector: %s", getattr(connection, "id", "?"), e,
        )
        return None
    finally:
        if reader is not None:
            reader.close()
        db.close()


def _validate_data_source(data_source: dict, widget_type: str, widget_index: int) -> str | None:
    """Validate optional dataSource field. Returns error message or None if valid."""
    if not isinstance(data_source, dict):
        return f"Widget at index {widget_index}: dataSource must be an object"

    if "connectionId" not in data_source:
        return f"Widget at index {widget_index}: dataSource missing required field: connectionId"
    if not isinstance(data_source["connectionId"], int):
        return f"Widget at index {widget_index}: dataSource.connectionId must be an integer"

    if "sql" not in data_source:
        return f"Widget at index {widget_index}: dataSource missing required field: sql"
    if not isinstance(data_source["sql"], str) or not data_source["sql"].strip():
        return f"Widget at index {widget_index}: dataSource.sql must be a non-empty string"

    if "mapping" not in data_source:
        return f"Widget at index {widget_index}: dataSource missing required field: mapping"
    mapping = data_source["mapping"]
    if not isinstance(mapping, dict):
        return f"Widget at index {widget_index}: dataSource.mapping must be an object"

    mapping_type = mapping.get("type")
    if mapping_type not in _VALID_MAPPING_TYPES:
        return (
            f"Widget at index {widget_index}: dataSource.mapping.type must be one of "
            f"{sorted(_VALID_MAPPING_TYPES)}"
        )
    if mapping_type != widget_type:
        return (
            f"Widget at index {widget_index}: dataSource.mapping.type '{mapping_type}' "
            f"must match widget.type '{widget_type}'"
        )

    return None


def _validate_widgets(widgets: list) -> str | None:
    """Validate widget list. Returns error message or None if valid."""
    for i, widget in enumerate(widgets):
        if not isinstance(widget, dict):
            return f"Widget at index {i} must be an object"
        if "id" not in widget:
            return f"Widget at index {i} missing required field: id"
        if "position" not in widget:
            return f"Widget at index {i} missing required field: position"
        if "widget" not in widget:
            return f"Widget at index {i} missing required field: widget"

        position = widget["position"]
        if not isinstance(position, dict):
            return f"Widget at index {i}: position must be an object"
        for field in ("x", "y", "w", "h"):
            if field not in position:
                return f"Widget at index {i}: position missing required field: {field}"

        widget_config = widget["widget"]
        if not isinstance(widget_config, dict):
            return f"Widget at index {i}: widget must be an object"
        if "type" not in widget_config:
            return f"Widget at index {i}: widget missing required field: type"
        if widget_config["type"] not in _VALID_WIDGET_TYPES:
            return f"Widget at index {i}: widget.type must be one of {sorted(_VALID_WIDGET_TYPES)}"

        # Validate optional dataSource for data widgets
        if "dataSource" in widget:
            error = _validate_data_source(widget["dataSource"], widget_config["type"], i)
            if error:
                return error

    return None


def _validate_widget_sql_schema(widgets: list, extra_connection_ids: list | None = None) -> list[str]:
    """
    Cross-reference widget SQL mapping columns against the schema for each connectionId.
    Returns a list of warning strings. Empty list means no issues found.

    ``extra_connection_ids`` — connections the agent can access but which may not
    be any widget's declared connectionId. Their schemas are merged into the
    table universe so a cross-connection JOIN (a connectionId=A widget that also
    references connection B's table, both on the shared data plane) validates
    instead of flagging B's table as "unknown".
    """
    from backend.services.schema_discovery import load_schema_file
    from backend.agents.sql_validation import (
        extract_table_refs, extract_cte_names, get_all_tables,
        validate_tables, validate_sql_columns, validate_mapping_columns,
    )

    # Collect unique connection IDs and load schemas
    connection_ids = {
        w["dataSource"]["connectionId"]
        for w in widgets
        if "dataSource" in w
    }
    if extra_connection_ids:
        connection_ids |= set(extra_connection_ids)
    schemas: dict[int, dict] = {}
    for cid in connection_ids:
        try:
            schemas[cid] = load_schema_file(cid)
        except FileNotFoundError:
            pass  # Schema not cached — skip validation for this connection

    if not schemas:
        return []

    # Merge every loaded connection schema into one table universe. Data-plane-
    # backed connections (google_sheets, dataset/CSV, data_plane) that share an
    # owner scope are queryable together, so a single widget's SQL may JOIN tables
    # from sibling connections — the connectionId only selects the shared scope.
    # Validate against the union so those joins don't read as "unknown table/
    # column". Live SQL connections simply won't share table names here, so this
    # stays advisory for them.
    from backend.agents.sql_validation import get_tables_dict
    merged_tables: dict = {}
    for _sj in schemas.values():
        _t = get_tables_dict(_sj)
        if isinstance(_t, list):
            for _x in _t:
                _nm = _x.get("name") if isinstance(_x, dict) else None
                if _nm:
                    merged_tables[_nm] = _x
        elif isinstance(_t, dict):
            merged_tables.update(_t)
    merged_schema = {"tables": merged_tables}
    all_schema_tables = get_all_tables(merged_schema)

    warnings: list[str] = []
    for w in widgets:
        if "dataSource" not in w:
            continue
        ds = w["dataSource"]
        cid = ds["connectionId"]
        sql = ds.get("sql", "")
        mapping = ds.get("mapping", {})
        widget_id = w.get("id", "?")

        # Validate against the merged scope universe, not just this widget's own
        # connectionId, so cross-connection joins over the shared plane are allowed.
        schema_json = merged_schema

        table_matches, table_aliases = extract_table_refs(sql)
        if not table_matches:
            continue

        cte_names = extract_cte_names(sql)
        known_virtual = cte_names | table_aliases
        referenced_table = table_matches[0].split(".")[-1]

        # Validate tables
        table_warnings = validate_tables(table_matches, known_virtual, all_schema_tables, widget_id)
        if table_warnings:
            warnings.extend(table_warnings)
            continue

        # Validate SQL columns
        col_warnings = validate_sql_columns(
            sql, schema_json, table_matches, table_aliases, all_schema_tables, widget_id,
        )
        if col_warnings:
            warnings.extend(col_warnings)
            continue  # Skip mapping validation — fix SQL first

        # Validate mapping columns
        mapping_warnings = validate_mapping_columns(
            sql, mapping, mapping.get("type", ""), schema_json,
            table_matches, referenced_table, widget_id,
        )
        warnings.extend(mapping_warnings)

    return warnings


# Chart types that operate on aggregated category data. Charts outside this
# set (e.g. scatter) take raw X/Y metric pairs and must not be forced through
# an aggregation check.
_CATEGORY_CHART_TYPES = {"bar", "pie", "line", "area", "doughnut"}

# Cheap pre-check for "does this SQL look aggregated?" — used by the
# `chart_not_aggregated` rule. Match GROUP BY at any depth (incl. CTEs) and
# any standard aggregate function. Intentionally permissive: a false negative
# is fine (the LLM will get a violation to fix); a false positive would block
# legitimate pre-aggregated charts.
_AGGREGATE_FN_RE = re.compile(
    r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(",
    re.IGNORECASE,
)
_GROUP_BY_RE = re.compile(r"\bGROUP\s+BY\b", re.IGNORECASE)


def _is_aggregated_sql(sql: str) -> bool:
    """True if SQL already aggregates (GROUP BY or a non-window aggregate fn).

    Parsed, not pattern-matched, for one reason: `SUM(x) OVER ()` is a window
    function. It matches the aggregate regex but returns one row per input row,
    each holding the same total, so a KPI over it clears the guard without an
    explicit aggregation and then gets summed again — a row-count-fold
    over-report. The regexes stay as the fallback for SQL the parser rejects.
    """
    if not isinstance(sql, str) or not sql.strip():
        return False
    try:
        import sqlglot
        from sqlglot import exp

        ast = sqlglot.parse_one(sql)
    except Exception:
        return bool(_GROUP_BY_RE.search(sql) or _AGGREGATE_FN_RE.search(sql))
    if ast is None:
        return bool(_GROUP_BY_RE.search(sql) or _AGGREGATE_FN_RE.search(sql))
    if ast.find(exp.Group):
        return True
    def _windowed(fn) -> bool:
        # Climb to the nearest Window or enclosing aggregate. Several analytic
        # forms put a wrapper node between the function and its OVER —
        # `SUM(x) FILTER (…) OVER ()` is Window(Filter(Sum)),
        # `FIRST_VALUE(x) IGNORE NULLS OVER ()` is Window(IgnoreNulls(FirstValue)),
        # `PERCENTILE_CONT(…) WITHIN GROUP (…) OVER ()` is Window(WithinGroup(…))
        # — so checking the immediate parent reads them all as real one-row
        # aggregates. Stopping the climb at an AggFunc keeps
        # `SUM(SUM(x)) OVER ()` aggregated, and requiring the climb to arrive in
        # the Window's own function slot keeps `RANK() OVER (ORDER BY SUM(x))`
        # aggregated too — that SUM sits in the window's ORDER BY, not under it.
        node, parent = fn, fn.parent
        while parent is not None and not isinstance(parent, (exp.Window, exp.AggFunc)):
            node, parent = parent, parent.parent
        return isinstance(parent, exp.Window) and parent.this is node

    return any(not _windowed(fn) for fn in ast.find_all(exp.AggFunc))


def cfg_title_for(wcfg: dict, fallback: str) -> str:
    """Best-effort human label for a widget's config — used in error messages
    so the LLM knows which widget the violation refers to."""
    if not isinstance(wcfg, dict):
        return fallback
    cfg = wcfg.get("config") or {}
    # `"".splitlines()` is `[]`, so indexing it raised IndexError for any widget
    # with no title, no label and no content — turning a violation into a crash.
    lines = (cfg.get("content") or "").splitlines()
    return (
        cfg.get("title")
        or cfg.get("label")
        or (lines[0][:40] if lines else "")
        or fallback
    )


def _datasetcolumns_aggregation_present(ds: dict | None) -> bool:
    """True if dataSource.mapping.datasetColumns declares an `aggregation` key
    on every entry — the escape hatch for pre-aggregated source tables."""
    if not isinstance(ds, dict):
        return False
    mapping = ds.get("mapping") or {}
    cols = mapping.get("datasetColumns") or []
    if not cols:
        return False
    return all(isinstance(c, dict) and "aggregation" in c for c in cols)


def _widgets_missing(tool_name: str) -> dict:
    """Reply for a save call that carries no widget list.

    Reaches the model instead of a validator's "widgets: Field required": on the
    2026-09-06 ladder four builds ended exactly there, the model re-issued the same
    call, and the orchestrator gave up. The message says what is missing, where it
    is not, and that re-issuing does not spend a build attempt.
    """
    return {
        "success": False,
        "code": "widgets_missing",
        "message": (
            "widgets is required: pass the full list of lean widget objects you designed "
            "(filter, kpi, chart, table, pivot_table, section). data_context does NOT carry "
            f"widgets. Call {tool_name} again now with the same title/description/data_context "
            "AND widgets — this is a missing argument, not a failed build attempt. If "
            "build_dashboard_context returned an error, surface that to the user instead of "
            f"calling {tool_name}."
        ),
    }


def _log_widget_count(tool_name: str, widgets: list) -> None:
    """Count how often a design exceeds the prompt's target — accepted, only logged."""
    from backend.agents.orchestrator.dashboard_widget_verifier import MAX_TOTAL_WIDGETS, data_widgets

    n_data = len(data_widgets(widgets))
    if n_data > MAX_TOTAL_WIDGETS:
        logger.info(
            "%s: %d data widgets (target <= %d) — accepted", tool_name, n_data, MAX_TOTAL_WIDGETS
        )


def _verify_widgets(widgets: list, data_context: dict | None) -> list[dict]:
    """Pre-persistence verification gate for create_dashboard / update_dashboard.

    Returns a list of structured per-widget violations. Empty list = clean.
    Consolidates structural checks (collecting ALL errors, not first-only) with
    the dashboard-level KPI / count rules so the LLM gets every error at once
    and can patch specific widgets in a single retry.
    """
    from backend.agents.orchestrator.dashboard_widget_verifier import verify_dashboard_widgets
    from backend.services.widget_transform import KPI_AGGREGATIONS

    violations: list[dict] = []

    for i, widget in enumerate(widgets):
        if not isinstance(widget, dict):
            violations.append({
                "widget_id": f"index_{i}",
                "code": "not_object",
                "message": f"Widget at index {i} must be an object.",
                "fix_hint": "Wrap the widget as a JSON object with id/position/widget keys.",
            })
            continue

        wid = widget.get("id") or f"index_{i}"

        for field in ("id", "position", "widget"):
            if field not in widget:
                violations.append({
                    "widget_id": wid,
                    "code": f"missing_{field}",
                    "message": f"Widget missing required field: {field}.",
                    "fix_hint": f"Add a top-level '{field}' field.",
                })

        pos = widget.get("position")
        if isinstance(pos, dict):
            for axis in ("x", "y", "w", "h"):
                if axis not in pos:
                    violations.append({
                        "widget_id": wid,
                        "code": f"position_missing_{axis}",
                        "message": f"position missing required field: {axis}.",
                        "fix_hint": f"Add position.{axis} (integer on the 12-column grid).",
                    })
        elif pos is not None:
            violations.append({
                "widget_id": wid,
                "code": "position_not_object",
                "message": "position must be an object.",
                "fix_hint": 'Use {"x": <col>, "y": <row>, "w": <span>, "h": <rows>}.',
            })

        wcfg = widget.get("widget")
        if isinstance(wcfg, dict):
            if "type" not in wcfg:
                violations.append({
                    "widget_id": wid,
                    "code": "widget_missing_type",
                    "message": "widget missing required field: type.",
                    "fix_hint": f"Set widget.type to one of {sorted(_VALID_WIDGET_TYPES)}.",
                })
            elif wcfg["type"] not in _VALID_WIDGET_TYPES:
                violations.append({
                    "widget_id": wid,
                    "code": "invalid_widget_type",
                    "message": f"widget.type='{wcfg['type']}' is not valid.",
                    "fix_hint": f"Use one of {sorted(_VALID_WIDGET_TYPES)}.",
                })
        elif wcfg is not None:
            violations.append({
                "widget_id": wid,
                "code": "widget_not_object",
                "message": "widget must be an object.",
                "fix_hint": 'Use {"type": <type>, "config": {...}}.',
            })

        if "dataSource" in widget and isinstance(wcfg, dict) and "type" in wcfg:
            ds_error = _validate_data_source(widget["dataSource"], wcfg["type"], i)
            if ds_error:
                violations.append({
                    "widget_id": wid,
                    "code": "invalid_dataSource",
                    "message": ds_error,
                    "fix_hint": "Fix the dataSource shape per the create_dashboard schema.",
                })
                # The guards below read dataSource keys: on a non-dict they crash,
                # on a missing sql they pile on noise. Shape errors first.
                continue

            # Aggregation guard for category charts. A bar/pie/line/area/doughnut
            # without GROUP BY, an aggregate fn, or `aggregation` on every
            # datasetColumns entry will return raw row-level data and render as
            # noise (thousands of repeated labels). Reject pre-execution so the
            # LLM can fix & retry. Scatter is exempt — it takes metric pairs.
            chart_type = (wcfg.get("config") or {}).get("type")
            if chart_type in _CATEGORY_CHART_TYPES and not _is_aggregated_sql(
                widget["dataSource"].get("sql") or ""
            ) and not _datasetcolumns_aggregation_present(widget["dataSource"]):
                violations.append({
                    "widget_id": wid,
                    "code": "chart_not_aggregated",
                    "message": (
                        f"Chart '{cfg_title_for(wcfg, wid)}' (type={chart_type}) "
                        "has no GROUP BY, no aggregate function, and no "
                        "datasetColumns[].aggregation — the SQL will return raw rows."
                    ),
                    "fix_hint": (
                        "Either (a) use GROUP BY + COUNT/SUM/AVG in the SQL, "
                        "or (b) set `aggregation` on each datasetColumns entry "
                        "(e.g. \"sum\") so the transform groups-by labelColumn. "
                        "Raw-row category charts (e.g. "
                        "`SELECT role, left FROM t WHERE left=1`) are rejected."
                    ),
                })

            # An aggregation the transform doesn't know is treated as absent
            # (see transform_kpi), so the intent behind e.g. "average" is lost
            # silently. Reject it whatever the SQL shape.
            if wcfg["type"] == "kpi":
                _kpi_agg = (widget["dataSource"].get("mapping") or {}).get("aggregation")
                if _kpi_agg is not None and _kpi_agg not in KPI_AGGREGATIONS:
                    violations.append({
                        "widget_id": wid,
                        "code": "kpi_invalid_aggregation",
                        "message": (
                            f"KPI '{cfg_title_for(wcfg, wid)}' has "
                            f"mapping.aggregation={_kpi_agg!r}, which is not a "
                            "supported method."
                        ),
                        "fix_hint": f"Use one of {'|'.join(sorted(KPI_AGGREGATIONS))}.",
                    })

            # Aggregation guard for KPIs. A KPI collapses the result to one
            # number: with neither SQL aggregation nor mapping.aggregation the
            # transform falls back to an arbitrary single row, so a 15k-row
            # scan renders as row 0's value. Reject pre-execution like the
            # chart rule above.
            if wcfg["type"] == "kpi" and not _is_aggregated_sql(
                widget["dataSource"].get("sql") or ""
            ) and not (widget["dataSource"].get("mapping") or {}).get("aggregation"):
                violations.append({
                    "widget_id": wid,
                    "code": "kpi_not_aggregated",
                    "message": (
                        f"KPI '{cfg_title_for(wcfg, wid)}' has no GROUP BY, no "
                        "aggregate function, and no mapping.aggregation — the "
                        "headline would be computed over raw rows the query "
                        "engine may have capped, so it can silently under-report."
                    ),
                    "fix_hint": (
                        "Either aggregate in SQL (SELECT SUM(...)/COUNT(*)) or "
                        "set mapping.aggregation "
                        "(sum|avg|count|countDistinct|min|max|last)."
                    ),
                })

            # Boundedness guard for scatter/bubble. Raw-row scatter SQL without
            # GROUP BY/aggregates and without LIMIT can return the whole table —
            # slow and unreadable (discrete metrics render as solid bands).
            if chart_type in ("scatter", "bubble"):
                _sc_sql = widget["dataSource"].get("sql") or ""
                _sc_map = widget["dataSource"].get("mapping") or {}
                _sc_has_agg = bool(
                    _sc_map.get("xAggregation") not in (None, "none")
                    or _sc_map.get("yAggregation") not in (None, "none")
                )
                if (not _is_aggregated_sql(_sc_sql) and not _sc_has_agg
                        and "limit" not in _sc_sql.lower()):
                    violations.append({
                        "widget_id": wid,
                        "code": "scatter_not_bounded",
                        "message": (
                            f"Chart '{cfg_title_for(wcfg, wid)}' (type={chart_type}) "
                            "has no GROUP BY/aggregate and no LIMIT — the SQL will "
                            "return every raw row."
                        ),
                        "fix_hint": (
                            "Preferred: one point per entity — GROUP BY a dimension "
                            "and aggregate both metrics (AVG/SUM). Otherwise add "
                            "LIMIT 1000 for a raw-row sample."
                        ),
                    })

    for rule_msg in verify_dashboard_widgets(widgets):
        violations.append({
            "widget_id": None,
            "code": "dashboard_rule",
            "message": rule_msg,
            # Not "apply the rules from the prompt" — that is circular, and the
            # agent burns a full regeneration round re-reading it.
            "fix_hint": (
                "Drop the surplus widgets from THIS list — do not regenerate the "
                "dashboard. Merge duplicate breakdowns of the same dimension, fold "
                "detail into the pivot_table, and keep at most one KPI per metric."
            ),
        })

    return violations


async def _attempt_sql_fix(
    sql: str,
    error_message: str,
    connection,
    mapping: dict,
    widget_id: str,
    widget_title: str | None = None,
    data_context: dict | None = None,
    sample_data: str = "",
) -> str | None:
    """Use LLM to fix a broken SQL query. Returns corrected SQL or None."""
    import re
    from backend.services.schema_discovery import load_schema_file
    from backend.services.schema_utils import extract_table_names, build_schema_summary
    from backend.llm.factory import get_provider
    from backend.config import settings

    schema_summary = ""
    try:
        schema_json = load_schema_file(connection.id)
        referenced_tables = extract_table_names(sql)
        schema_summary = build_schema_summary(schema_json, referenced_tables)
    except FileNotFoundError:
        logger.warning(f"Widget '{widget_id}': schema file not found for connection {connection.id}, fixing without schema")

    mapping_info = ', '.join(f"{k}={v}" for k, v in mapping.items() if k != 'type')
    mapping_type = mapping.get('type', 'unknown')

    title_context = f"\nWidget title: {widget_title}" if widget_title else ""

    reg = get_connector_registration(connection.db_type)
    db_type_display = reg.sql_dialect_hint if reg and reg.sql_dialect_hint else str(connection.db_type)

    prompt = f"""You are a SQL expert. Fix the SQL query that produced an error.

Original SQL:
```sql
{sql}
```

Error:
{error_message}

Widget type: {mapping_type}
Expected output columns: {mapping_info}
Database type: {db_type_display}{title_context}
IMPORTANT: Only use table and column names that exist in the schema below. Do NOT invent table or column names.
"""

    if title_context:
        prompt += """
SEMANTIC CHECK: The fixed SQL must correctly query data that matches the widget title.
For example, if the title says "Average Price", the SQL must query a price-related column — not floor_area, size, or other unrelated columns.
"""

    if schema_summary:
        prompt += f"\nDatabase schema:\n{schema_summary}\n"

    if data_context and data_context.get("baseJoin"):
        prompt += f"\nBase join context:\n{json.dumps(data_context['baseJoin'], indent=2)}\n"

    if sample_data:
        prompt += f"\nSample data from referenced tables:\n{sample_data}\n"

    prompt += """
SQL validation rules (your output must comply):
- Query must start with SELECT or WITH (single statement only)
- Forbidden keywords: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, GRANT, REVOKE, EXEC, EXECUTE, COPY, LOAD, SET, CALL, RENAME
- String functions like REPLACE(), SUBSTRING(), TRIM() are allowed

Return ONLY a JSON object with this exact structure (no markdown, no extra text):
{"suggested_sql": "...", "explanation": "..."}

The explanation should be one sentence describing what was wrong and what was changed."""

    try:
        provider = get_provider(settings.default_llm_provider)
        messages = [{"role": "user", "content": prompt}]
        response = await provider.chat(messages, temperature=0.2)
        content = response.strip()

        if content.startswith("```"):
            content = re.sub(r'^```[a-z]*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()

        result = json.loads(content)
        return result.get("suggested_sql")
    except Exception as e:
        logger.warning(f"Widget '{widget_id}': LLM SQL fix attempt failed: {e}")
        return None


# Widget configs are persisted as JSONB and shipped to the browser — cap raw
# result rows so an unaggregated SELECT can't bloat the dashboard payload.
MAX_WIDGET_RESULT_ROWS = 5000


def _cap_widget_rows(result, widget_id):
    if result.row_count > MAX_WIDGET_RESULT_ROWS:
        logger.warning(
            f"Widget '{widget_id}': SQL returned {result.row_count} rows; truncating to "
            f"{MAX_WIDGET_RESULT_ROWS}. The widget SQL should aggregate instead of returning raw rows."
        )
        result.rows = result.rows[:MAX_WIDGET_RESULT_ROWS]
        result.row_count = MAX_WIDGET_RESULT_ROWS
        result.truncated = True
    return result


def _mark_widget_failed(widget: dict, error: str) -> None:
    """Record an unrecoverable SQL failure on the widget's own config.

    Without this the widget ships with no `rows`/`value` at all, which renders
    as an empty table — indistinguishable from "no data" when it actually means
    "broken SQL". The error rides in the persisted widget JSON so the dashboard
    can say so instead of showing a blank.
    """
    config = widget.setdefault("widget", {}).setdefault("config", {})
    config["error"] = f"Query failed: {error}"[:500]


def _resolve_widget_connections(connection_ids, user_id: str | None, db_session_factory: Callable) -> dict:
    """Resolve {connection_id: (connection, connector)} once per dashboard build.

    Must run inside asyncio.to_thread: connector construction does sync DB I/O
    (data-plane resolution opens its own session). When it ran per-widget on
    the event loop inside _execute_widget_sql, pool starvation deadlocked the
    loop — the coroutine that releases pooled connections was itself blocked
    waiting on the pool (prod freeze at 12 concurrent flows, 2026-07-30).

    One short-lived session loads all connection rows and is closed before any
    connector is built, so no transaction is pinned across plane resolution.
    The detached rows stay readable (column attrs are already loaded). IDs the
    user can't read are simply absent from the result — callers treat a miss
    as "not found", same as the old per-widget query.

    Only plane-backed connectors (serves_from_plane) are shared by widgets;
    source connectors hold a single lazy DBAPI connection, so
    _execute_widget_sql builds a private one per widget and only uses the row
    from this map. Connectors here are closed once by the fan-out caller.

    The SQL dialect rides in the map too: computing it per widget would put
    feature_flags.enabled() — a sync Redis GET with an on-miss Postgres load —
    back on the event loop, the exact I/O this resolver exists to keep off it.
    """
    from backend.models.database_connection import DatabaseConnection
    from backend.services.seed import readable_connection_clause

    ids = [_coerce_connection_id(cid) for cid in set(connection_ids) if cid is not None]
    if not ids:
        return {}

    db = db_session_factory()
    try:
        filters = [DatabaseConnection.id.in_(ids)]
        if user_id:
            filters.append(readable_connection_clause(user_id))
        rows = db.query(DatabaseConnection).filter(*filters).all()
    finally:
        db.close()

    resolved = {}
    for connection in rows:
        connector = get_connector_for_connection(connection)
        resolved[connection.id] = (connection, connector, _widget_sql_dialect(connection, connector))
    return resolved


def _coerce_connection_id(cid):
    """Match Postgres' implicit cast: widget JSON may carry connectionId as a
    digit string, which the old per-widget SQL lookup coerced server-side. The
    resolved map is keyed by the int PK, so coerce before any dict lookup."""
    if isinstance(cid, str) and cid.isdigit():
        return int(cid)
    return cid


def _resolve_one_connection(connection_id, user_id, db_session_factory):
    """Sync fallback for callers that didn't pre-resolve. Returns (connection, connector, dialect) or (None, None, "")."""
    resolved = _resolve_widget_connections([connection_id], user_id, db_session_factory)
    return resolved.get(_coerce_connection_id(connection_id), (None, None, ""))


async def _execute_widget_sql(widget: dict, db_session_factory: Callable, data_context: dict | None = None, user_id: str | None = None, resolved: dict | None = None, allow_row_sampling: bool = True) -> str | None:
    """
    Execute the dataSource SQL for a widget and merge results into widget.widget.config.

    Modifies widget in-place. On first failure, attempts an LLM-powered SQL fix and retries once,
    including sample data and baseJoin context for better fix quality.
    Returns error string if both attempts fail, None on success.

    `allow_row_sampling=False` drops the sampled rows from that fix prompt (schema
    + error + baseJoin only) — for callers whose contract is that no row data
    reaches an LLM at all.

    `resolved` is the {connection_id: (connection, connector)} map from
    _resolve_widget_connections. Callers fanning out over multiple widgets must
    pass it — per-widget resolution costs 3 Postgres round-trips each and, run
    concurrently, re-creates the pool contention this map exists to avoid. The
    fallback resolves inline (in a worker thread) and owns the connector's close;
    pre-resolved connectors are closed by the caller after the fan-out.
    """
    from backend.services.schema_utils import normalize_sql_for
    from backend.services.widget_transform import transform_widget_data

    data_source = widget.get("dataSource")
    if not data_source:
        return

    connection_id = data_source.get("connectionId")
    sql = data_source.get("sql")
    mapping = data_source.get("mapping")
    # Inject chartType so scatter charts produce {x,y} points
    chart_type = widget.get("widget", {}).get("config", {}).get("type")
    if chart_type and mapping and "chartType" not in mapping:
        mapping = {**mapping, "chartType": chart_type}
        data_source["mapping"] = mapping
    widget_id = widget.get("id")
    widget_title = widget.get("widget", {}).get("config", {}).get("title") or widget.get("widget", {}).get("config", {}).get("label")

    if resolved is None:
        # No pre-resolved map (single-widget callers, tests). The lookup +
        # connector construction do sync DB I/O — keep them off the event loop.
        connection, connector, dialect = await asyncio.to_thread(
            _resolve_one_connection, connection_id, user_id, db_session_factory
        )
        owns_connector = True
    else:
        # A supplied map covers every connection id in the build, so a missing
        # key means the row is absent or unreadable — NOT a reason to re-query.
        # Falling back here would re-run the same filtered lookup for the same
        # empty result, per widget, which is the contention this map removes.
        pre = resolved.get(_coerce_connection_id(connection_id))
        connection, shared_connector, dialect = pre if pre else (None, None, "")
        if getattr(shared_connector, "serves_from_plane", False):
            # Plane-backed connectors route through a thread-safe BigQuery/
            # DuckDB client — safe to share across the concurrent fan-out.
            connector, owns_connector = shared_connector, False
        else:
            # Source connectors (base.py) hold ONE lazy DBAPI connection;
            # sharing one across concurrent widgets would interleave cursors
            # on it. Construction is pure kwargs (the lazy connect happens
            # inside to_thread on first query) — build one per widget.
            connector = (
                await asyncio.to_thread(get_connector_for_connection, connection)
                if connection is not None else None
            )
            owns_connector = True
    if connection is None:
        logger.warning(f"Widget '{widget_id}': connection {connection_id} not found, skipping SQL execution")
        return
    try:
        # The agent writes ANSI-quoted identifiers regardless of the execution
        # surface, so `c."role"` is a string literal on BigQuery and a column
        # named `left` is a syntax error anywhere. Fix deterministically before
        # falling back to the (slow, unreliable) LLM repair below. The dialect
        # comes from the resolver — computing it here would put the feature-flag
        # Redis/Postgres reads back on the event loop.
        normalized_sql = normalize_sql_for(sql, dialect)

        try:
            result = await asyncio.to_thread(_run_widget_query, connection, normalized_sql, db_session_factory, connector)
            # KPI collapses to a single number, so a second local cut here
            # would only hide the engine's own `truncated` flag from
            # transform_kpi, which refuses to aggregate a truncated result.
            # Charts and tables still cap — their config embeds one entry per row.
            if (mapping or {}).get("type") != "kpi":
                result = _cap_widget_rows(result, widget_id)
            config = transform_widget_data(result, mapping)
            widget["widget"]["config"].update(config)
            # Persist so the serve path (api/widget_data) gets the fixed SQL too,
            # instead of re-failing on every dashboard load.
            if normalized_sql != sql:
                data_source["sql"] = normalized_sql
            logger.info(f"Widget '{widget_id}': SQL executed, config populated with {result.row_count} rows")
            return
        except Exception as e:
            first_error_msg = str(e)
            logger.warning(f"Widget '{widget_id}': SQL execution failed, attempting LLM fix: {first_error_msg}")

        # Gather sample data from referenced tables for better fix context.
        # Privacy: under metadata_only_llm, skip sampling entirely — the fix
        # prompt keeps the error + schema + baseJoin, no real rows. Callers that
        # promise no row data ever reaches an LLM (chat charts) pass
        # allow_row_sampling=False for the same effect regardless of the flag.
        sample_data = ""
        from backend.services.llm_privacy import metadata_only_for_connection
        # to_thread: reads the org feature-flag cache (sync Redis + on-miss
        # Postgres) — same event-loop hazard as the dialect computation.
        if allow_row_sampling and not await asyncio.to_thread(metadata_only_for_connection, connection):
            try:
                from backend.services.schema_utils import extract_table_names
                tables = extract_table_names(sql)
                for tbl in list(tables)[:2]:
                    try:
                        sample_sql = normalize_sql_for(f'SELECT * FROM "{tbl}" LIMIT 3', dialect)
                        sample_result = await asyncio.to_thread(
                            _run_widget_query, connection, sample_sql, db_session_factory, connector,
                        )
                        sample_data += f"\nTable '{tbl}' sample:\n"
                        sample_data += f"  Columns: {sample_result.columns}\n"
                        for srow in sample_result.rows[:3]:
                            sample_data += f"  {list(srow)}\n"
                    except Exception:
                        pass
            except Exception:
                pass

        # Attempt LLM-powered SQL fix with sample data + baseJoin context
        fixed_sql = await _attempt_sql_fix(
            sql=normalized_sql,
            error_message=first_error_msg,
            connection=connection,
            mapping=mapping,
            widget_id=widget_id,
            widget_title=widget_title,
            data_context=data_context,
            sample_data=sample_data,
        )

        if not fixed_sql:
            logger.warning(f"Widget '{widget_id}': LLM fix returned no SQL, using LLM-provided config")
            _mark_widget_failed(widget, first_error_msg)
            return first_error_msg

        logger.info(f"Widget '{widget_id}': SQL fix attempted, retrying with corrected SQL")
        fixed_sql = normalize_sql_for(fixed_sql, dialect)
        try:
            result = await asyncio.to_thread(_run_widget_query, connection, fixed_sql, db_session_factory, connector)
            # KPI collapses to a single number, so a second local cut here
            # would only hide the engine's own `truncated` flag from
            # transform_kpi, which refuses to aggregate a truncated result.
            # Charts and tables still cap — their config embeds one entry per row.
            if (mapping or {}).get("type") != "kpi":
                result = _cap_widget_rows(result, widget_id)
            config = transform_widget_data(result, mapping)
            widget["widget"]["config"].update(config)
            # Persist the fixed SQL back to the widget's dataSource
            data_source["sql"] = fixed_sql
            logger.info(f"Widget '{widget_id}': SQL fix succeeded, config populated with {result.row_count} rows")
            return None
        except Exception as retry_error:
            error_msg = f"Original: {first_error_msg} | Retry: {retry_error}"
            logger.warning(f"Widget '{widget_id}': SQL fix also failed, using LLM-provided config. {error_msg}")
            _mark_widget_failed(widget, error_msg)
            return error_msg
    finally:
        # Pre-resolved connectors are shared across widgets; the fan-out caller
        # closes them once after gather. Only the inline fallback owns its own.
        if owns_connector and connector:
            connector.close()


def build_inline_dashboard_tools(context: AgentContext, db_session_factory: Callable) -> List:
    """Return [create_dashboard, update_dashboard] tools bound to context and db_session_factory.

    These tools execute the dashboard creation/update inline (validate widgets, run
    SQL, persist) — distinct from the orchestrator's `build_dashboard_tools`, which
    delegates to the dashboard sub-agent via `invoke_dashboard_agent`.
    """
    if db_session_factory is None:
        return []

    from langchain_core.tools import tool
    from backend.models.dashboard import Dashboard

    @tool
    async def create_dashboard(title: str, description: str, widgets: list[dict] | None = None, data_context: dict | None = None) -> str:
        """
        Create a new dashboard with widgets and persist it to the database.

        Emit LEAN widgets — one flat param object per widget. The backend hydrates
        them into full widget JSON: it wraps the type/config/dataSource envelope,
        derives the dataSource mapping from your params, and assigns grid positions
        automatically. Do NOT output position/x/y/w/h, the "widget" wrapper, or a
        "mapping" object — those are added for you. For SQL-backed widgets the SQL
        is auto-executed and the config is populated with live data.

        Args:
            title: Dashboard title (e.g. "Property Overview Dashboard")
            description: Brief description of what the dashboard shows
            widgets: List of LEAN widget objects, in top-to-bottom reading order.
                Each is a flat object: {"type": <widget_type>, ...params}. Call
                get_widget_spec("all") for the full param list per type.

                EXACT shape (lean):
                [
                  {"type": "filter", "controls": [
                     {"type": "date_range", "label": "Date", "key": "date", "column": "order_date",
                      "dateRangeSource": {"connectionId": 1, "sql": "SELECT MIN(o.order_date) AS min_date, MAX(o.order_date) AS max_date FROM orders o"},
                      "dateRangeDefault": "full"}]},
                  {"type": "kpi", "label": "Total Revenue", "prefix": "$", "valueColumn": "revenue",
                   "aggregation": "sum", "connectionId": 1, "sql": "SELECT SUM(o.amount) AS revenue FROM orders o",
                   "sources": ["orders"]},
                  {"type": "chart", "chartType": "bar", "title": "Revenue by Region",
                   "labelColumn": "region",
                   "datasetColumns": [{"column": "revenue", "label": "Revenue", "aggregation": "sum"}],
                   "options": {"sortBy": "value", "sortDirection": "desc"},
                   "connectionId": 1, "sql": "SELECT o.region, SUM(o.amount) AS revenue FROM orders o GROUP BY o.region",
                   "sources": ["orders"]},
                  {"type": "section", "title": "Detail"},
                  {"type": "table", "title": "Top Orders",
                   "columns": [{"column": "order_id", "label": "Order"},
                               {"column": "amount", "label": "Amount", "sortable": true, "format": "currency"}],
                   "connectionId": 1, "sql": "SELECT order_id, amount FROM orders ORDER BY amount DESC LIMIT 20",
                   "sources": ["orders"]}
                ]

                Per-type params (flat — no nested config/mapping):
                - kpi: label*, valueColumn*, aggregation?, prefix?, suffix?, connectionId*, sql*, sources?
                - chart: chartType*, title?, labelColumn?, datasetColumns* [{column,label}],
                    options? {stacked, indexAxis, showValues, showLegend, legendPosition, sortBy,
                    sortDirection}, connectionId*, sql*, sources?
                - table: columns* [{column, label, sortable?, format?}] (write each column ONCE),
                    title?, connectionId*, sql*, sources?
                - pivot_table: rowDimensions* [{column,label}], columnDimensions? (max 2),
                    values* [{column, label, aggregation}], title?, connectionId*, sql*, sources?
                - section: title* (plain text section header), sectionColor?
                - text: content* (markdown narrative only — headers use section), alignment?
                - filter: controls* [{type, label, key, column*, optionsSource {connectionId, sql} for dropdown}]
                  (filter has NO connectionId/sql/mapping at widget level)
                * = required.

                CROSS-CONNECTION JOINS: connections backed by the shared data
                plane (google_sheets, dataset/CSV, data_plane) that belong to the
                same user/org resolve to ONE query scope. A single widget MAY JOIN
                tables from several such connections in one SQL — set connectionId
                to any one of them (it selects the shared scope) and reference each
                table by its real name. NEVER stub a joined table's columns as NULL
                — write the real JOIN. The join executes; it is NOT a limitation.
                This does NOT apply to live SQL connections (postgres, mysql).

                WORKED EXAMPLE — table joining two Google Sheets connections
                (Sales = gsheets_48_sheet1, Inventory = gsheets_49_sheet1):
                  {"type": "table", "title": "Sales vs Inventory by Item",
                   "columns": [{"column": "item_name", "label": "Item"},
                               {"column": "buyer", "label": "Buyer"},
                               {"column": "units_sold", "label": "Units Sold"},
                               {"column": "stock_on_hand", "label": "Stock"},
                               {"column": "price", "label": "Price", "format": "currency"}],
                   "connectionId": 48,
                   "sql": "SELECT i.item_name, s.buyer, s.quantity AS units_sold, i.quantity AS stock_on_hand, i.price FROM gsheets_48_sheet1 s JOIN gsheets_49_sheet1 i ON s.item_code = i.item_code",
                   "sources": ["gsheets_48_sheet1", "gsheets_49_sheet1"]}
                Note the real columns from BOTH tables in the SELECT — no NULLs.

                Layout: emit widgets in the order they should read top-to-bottom
                (filter → 3-5 KPIs → section → 3-5 charts → section → 1-2 tables).
                The backend packs each row to 12 columns. To emphasize ONE hero
                chart, optionally set its "width" (e.g. 8) and the next chart's
                "width" (e.g. 4); otherwise omit width. To preserve a widget across
                an update, include its "id". Target 9-15 data widgets (kpi, chart,
                table, pivot_table, filter); section and text headers are not counted.
                More are accepted and laid out automatically — prefer richer widgets
                over more of them.

                The backend fills only STRUCTURE (envelope, position, mapping wiring,
                styling defaults). YOU must still make every design choice — chart
                type, aggregation, chart options (sortBy/indexAxis/sliceLabel/stacked),
                the 3-5 KPI exec-summary row — and emit them as params. Minimal
                params ≠ skip design. Category charts (bar/pie/line/area) MUST
                aggregate: either `GROUP BY` + `COUNT/SUM/AVG` in the SQL, OR set
                `aggregation` on each `datasetColumns` entry (e.g. "sum").

            data_context: Optional dict from build_dashboard_context. If provided,
                stored on the dashboard for dimension-aware filtering.

        Returns:
            JSON with success, dashboard_id, and message
        """
        if not isinstance(widgets, list) or not widgets:
            return json.dumps(_widgets_missing("create_dashboard"))

        # Hydrate lean agent params into full widget JSON (envelope + derived
        # mapping + seed position) before any validation/SQL/persistence.
        from backend.agents.dashboard_agent.widget_specs.widgets import build_widgets
        widgets = build_widgets(widgets)
        _log_widget_count("create_dashboard", widgets)

        # Pre-persistence verification gate (Bug 5).
        # Consolidates structural validation, KPI dedupe / count caps. Returns
        # ALL violations as structured per-widget objects so the LLM can fix
        # specific widgets and retry — no first-error-only opacity.
        violations = _verify_widgets(widgets, data_context)
        if violations:
            logger.warning(
                "create_dashboard rejected: %s",
                "; ".join(f"{v.get('widget_id')}:{v.get('code')}" for v in violations),
            )
            return json.dumps({
                "success": False,
                "violations": violations,
                "message": (
                    "Validation failed — see violations. Fix the listed "
                    "widgets and call create_dashboard again."
                ),
            })

        # Deep-copy before any mutation: `widgets` IS the tool-call args object
        # held in the agent's message history. _execute_widget_sql merges query
        # results into widget.config in-place — without the copy those rows leak
        # into the replayed tool_call arguments and blow the provider's request
        # size limit on the next model call.
        import copy
        widgets = copy.deepcopy(widgets)

        # Deterministic layout pass: fill each grid row to 12 columns,
        # resolve overlaps, compact vertical gaps. Runs after the verifier
        # (positions guaranteed present) and before SQL/persistence so every
        # downstream step sees final positions.
        widgets = normalize_dashboard_layout(widgets)

        # Verify connection access for any SQL-backed widgets
        for w in widgets:
            if "dataSource" in w:
                cid = w["dataSource"]["connectionId"]
                if not context.can_access_connection(cid):
                    return json.dumps({
                        "success": False,
                        "message": f"Connection {cid} in dataSource is not accessible to you.",
                    })

        # Guard: reject dataset connections when CSV connector plugin is not loaded
        from backend.agents.tool_registry import get_plugin_tool_builders
        plugin_builders = get_plugin_tool_builders()
        csv_plugin_loaded = "create_dataset_from_upload" in plugin_builders
        if not csv_plugin_loaded:
            from backend.models.database_connection import DatabaseConnection as _DC
            _guard_db = db_session_factory()
            try:
                ds_cids = {w["dataSource"]["connectionId"] for w in widgets if "dataSource" in w}
                for cid in ds_cids:
                    conn = _guard_db.query(_DC).filter(_DC.id == cid).first()
                    if conn and conn.db_type == "dataset":
                        return json.dumps({
                            "success": False,
                            "message": (
                                f"Connection {cid} is a dataset connection. "
                                "Dataset dashboards require the CSV connector enterprise plugin."
                            ),
                        })
            except Exception:
                pass  # Guard is best-effort; don't block on DB errors
            finally:
                _guard_db.close()

        # Validate mapping columns against schema (warnings only — SQL execution is the real test)
        schema_warnings = _validate_widget_sql_schema(widgets, getattr(context, "available_connections", None))
        if schema_warnings:
            logger.warning("Schema validation warnings for '%s': %s", title, "; ".join(schema_warnings))

        # Auto-execute SQL for SQL-backed widgets and populate config.
        # Widgets are independent, so run them concurrently — bounded to avoid
        # hammering the source DB. Connections/connectors are resolved ONCE
        # before the fan-out, in a worker thread: resolved per-widget on the
        # event loop, the sync lookups deadlocked the loop under pool
        # starvation (see _resolve_widget_connections).
        sql_widgets = [w for w in widgets if "dataSource" in w]
        resolved = await asyncio.to_thread(
            _resolve_widget_connections,
            {w["dataSource"]["connectionId"] for w in sql_widgets},
            context.user_id,
            db_session_factory,
        ) if sql_widgets else {}
        try:
            sem = asyncio.Semaphore(5)

            async def _exec_bounded(w):
                async with sem:
                    await _execute_widget_sql(w, db_session_factory, data_context=data_context, user_id=context.user_id, resolved=resolved)

            await asyncio.gather(*[_exec_bounded(w) for w in sql_widgets])
        finally:
            for _conn, _connector, _dialect in resolved.values():
                try:
                    _connector.close()
                except Exception:
                    pass

        db = db_session_factory()
        try:
            # Stamp the owner's org so the dashboard is org-scoped like the
            # api/dashboards.create_dashboard path. Without it the row is
            # org_id=NULL, which breaks org-scoped visibility and the
            # shared-with-me connection resolution for cross-org viewers.
            from backend.services.dashboard_cache import _get_org_for_user
            org_id = _get_org_for_user(context.user_id)
            dashboard = Dashboard(
                user_id=context.user_id,
                org_id=org_id,
                title=title,
                description=description or None,
                widgets=widgets,
                data_context=data_context,
            )
            db.add(dashboard)
            db.commit()
            db.refresh(dashboard)

            # When the Org is cut over to DuckDB serving, the agent emits DuckDB
            # SQL — mark this dashboard born-DuckDB so the read path may serve it
            # via DuckDB-over-DataPlane immediately. Mirrors
            # api/dashboards.create_dashboard, which the agent's create path
            # bypasses (it persists the Dashboard directly).
            try:
                from backend.config.feature_flags import enabled
                if org_id and enabled(str(org_id), "duckdb_widget_serving"):
                    from backend.migration.dialect_migration import mark_born_duckdb
                    mark_born_duckdb(dashboard.id, db)
            except Exception:
                logger.warning(
                    "mark_born_duckdb failed for dashboard %s", dashboard.id, exc_info=True
                )

            # Dispatch async cache materialization (non-blocking)
            try:
                from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
                execute_dashboard_refresh.delay(dashboard.id)
                logger.info(f"Dispatched materialization task for new dashboard {dashboard.id}")
            except Exception as mat_err:
                logger.warning(f"Failed to dispatch materialization for dashboard {dashboard.id}: {mat_err}")

            response = {
                "success": True,
                "dashboard_id": dashboard.id,
                "message": f"Dashboard '{title}' created with {len(widgets)} widget(s). Navigate to /dashboard to view it.",
            }
            if schema_warnings:
                response["warnings"] = schema_warnings
                response["message"] += (
                    f"\n\nNote: {len(schema_warnings)} widget(s) had SQL column warnings — "
                    "their data may be incomplete. Fix the SQL for these widgets and call "
                    "update_dashboard to update them."
                )
            return json.dumps(response)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create dashboard: {e}")
            return json.dumps({"success": False, "message": f"Database error: {e}"})
        finally:
            db.close()

    @tool
    async def update_dashboard(dashboard_id: int, widgets: list | None = None, title: str = "", description: str = "", data_context: dict | None = None) -> str:
        """
        Update an existing dashboard's widgets, title, and/or description.

        Use this tool instead of create_dashboard when modifying an existing dashboard.
        The widgets list must contain the COMPLETE updated widget array (not just changes).
        For SQL-backed widgets, SQL is auto-executed just like create_dashboard.

        Args:
            dashboard_id: ID of the dashboard to update (get from list_dashboards)
            widgets: COMPLETE list of LEAN widget objects, same flat format as
                create_dashboard ({"type": <type>, ...params}; no position/envelope/
                mapping). Include each widget's "id" to preserve it across the update
                (so unchanged widgets keep their identity for animation/diffing).
            title: New dashboard title (empty string keeps the existing title)
            description: New dashboard description (empty string keeps the existing description)

        Returns:
            JSON with success, dashboard_id, and message
        """
        if not isinstance(widgets, list) or not widgets:
            return json.dumps(_widgets_missing("update_dashboard"))

        logger.info(f"update_dashboard called: dashboard_id={dashboard_id}, widget_count={len(widgets)}")

        # Hydrate lean agent params into full widget JSON (same as create_dashboard).
        from backend.agents.dashboard_agent.widget_specs.widgets import build_widgets
        widgets = build_widgets(widgets)
        _log_widget_count("update_dashboard", widgets)

        # Pre-persistence verification gate (Bug 5). Same gate as create_dashboard
        # so updates can't bypass the KPI / structural rules.
        violations = _verify_widgets(widgets, data_context)
        if violations:
            logger.warning(
                "update_dashboard rejected: %s",
                "; ".join(f"{v.get('widget_id')}:{v.get('code')}" for v in violations),
            )
            return json.dumps({
                "success": False,
                "violations": violations,
                "message": (
                    "Validation failed — see violations. Fix the listed "
                    "widgets and call update_dashboard again."
                ),
            })

        # Deep-copy before any mutation — same reason as create_dashboard: the
        # args object lives in the agent's message history and must not receive
        # the query-result rows merged into widget.config below.
        import copy
        widgets = copy.deepcopy(widgets)

        # Same deterministic layout pass as create_dashboard. Only positions
        # change, so the widget-id-keyed SQL diff below is unaffected.
        widgets = normalize_dashboard_layout(widgets)

        # Verify connection access for any SQL-backed widgets
        for w in widgets:
            if "dataSource" in w:
                cid = w["dataSource"]["connectionId"]
                if not context.can_access_connection(cid):
                    return json.dumps({
                        "success": False,
                        "message": f"Connection {cid} in dataSource is not accessible to you.",
                    })

        # Validate mapping columns against schema (warnings only — SQL execution is the real test)
        schema_warnings = _validate_widget_sql_schema(widgets, getattr(context, "available_connections", None))
        if schema_warnings:
            logger.warning("Schema validation warnings for dashboard %d: %s", dashboard_id, "; ".join(schema_warnings))

        # Load existing dashboard to compare SQL and carry over unchanged widget data
        db = db_session_factory()
        try:
            dashboard = db.query(Dashboard).filter(
                Dashboard.id == dashboard_id,
                Dashboard.user_id == context.user_id,
            ).first()
            if not dashboard:
                return json.dumps({"success": False, "message": f"Dashboard {dashboard_id} not found or not accessible."})

            # Build map of existing widget SQL and config for comparison
            existing_widgets_map = {}
            for ew in (dashboard.widgets or []):
                existing_widgets_map[ew.get("id")] = ew
        finally:
            db.close()

        # Only execute SQL for widgets whose SQL changed or that are new
        sql_changed = False
        to_execute = []
        for w in widgets:
            if "dataSource" not in w:
                continue
            new_sql = w["dataSource"].get("sql")
            new_conn = w["dataSource"].get("connectionId")
            existing_w = existing_widgets_map.get(w.get("id"))
            old_sql = existing_w.get("dataSource", {}).get("sql") if existing_w else None
            old_conn = existing_w.get("dataSource", {}).get("connectionId") if existing_w else None

            if old_sql == new_sql and old_sql is not None and old_conn == new_conn:
                # SQL unchanged — carry over existing computed data instead of re-executing
                existing_config = existing_w.get("widget", {}).get("config", {})
                w_config = w.get("widget", {}).get("config", {})
                for key in ("data", "rows", "value"):
                    if key in existing_config:
                        w_config[key] = existing_config[key]
                logger.info(f"Skipping SQL execution for unchanged widget '{w.get('id')}'")
            else:
                sql_changed = True
                to_execute.append(w)

        if to_execute:
            # Independent widgets — run concurrently, bounded. Same pre-resolve
            # pattern as create_dashboard (see _resolve_widget_connections).
            resolved = await asyncio.to_thread(
                _resolve_widget_connections,
                {w["dataSource"]["connectionId"] for w in to_execute},
                context.user_id,
                db_session_factory,
            )
            try:
                sem = asyncio.Semaphore(5)

                async def _exec_bounded(w):
                    async with sem:
                        await _execute_widget_sql(w, db_session_factory, data_context=data_context, user_id=context.user_id, resolved=resolved)

                await asyncio.gather(*[_exec_bounded(w) for w in to_execute])
            finally:
                for _conn, _connector, _dialect in resolved.values():
                    try:
                        _connector.close()
                    except Exception:
                        pass

        db = db_session_factory()
        try:
            dashboard = db.query(Dashboard).filter(
                Dashboard.id == dashboard_id,
                Dashboard.user_id == context.user_id,
            ).first()
            if not dashboard:
                return json.dumps({"success": False, "message": f"Dashboard {dashboard_id} not found or not accessible."})

            from sqlalchemy.orm.attributes import flag_modified

            if title:
                dashboard.title = title
            if description:
                dashboard.description = description
            dashboard.widgets = widgets
            flag_modified(dashboard, "widgets")
            if data_context is not None:
                dashboard.data_context = data_context
                flag_modified(dashboard, "data_context")

            db.commit()
            db.refresh(dashboard)

            # Dispatch async cache materialization only if SQL/connections changed
            if sql_changed:
                try:
                    from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
                    execute_dashboard_refresh.delay(dashboard.id)
                    logger.info(f"Dispatched materialization task for updated dashboard {dashboard.id}")
                except Exception as mat_err:
                    logger.warning(f"Failed to dispatch materialization for dashboard {dashboard.id}: {mat_err}")

            response = {
                "success": True,
                "dashboard_id": dashboard.id,
                "message": f"Dashboard '{dashboard.title}' updated with {len(widgets)} widget(s). Navigate to /dashboard to view it.",
            }
            if schema_warnings:
                response["warnings"] = schema_warnings
                response["message"] += (
                    f"\n\nNote: {len(schema_warnings)} widget(s) had SQL column warnings — "
                    "their data may be incomplete."
                )
            return json.dumps(response)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update dashboard: {e}")
            return json.dumps({"success": False, "message": f"Database error: {e}"})
        finally:
            db.close()

    return [create_dashboard, update_dashboard]


def build_create_dashboard_tool(context: AgentContext) -> List:
    """Registry-compatible wrapper: imports SessionLocal and delegates to build_inline_dashboard_tools."""
    from backend.database.session import SessionLocal
    return build_inline_dashboard_tools(context, SessionLocal)
