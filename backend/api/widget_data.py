import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.models.dashboard import Dashboard
from backend.schemas.widget_data import FilterParam, WidgetRefreshRequest, WidgetRefreshResponse, BulkRefreshRequest, BulkRefreshResponse, WidgetSuggestFixRequest, WidgetSuggestFixResponse
from backend.services.schema_utils import normalize_sql_for
from backend.services.widget_transform import transform_widget_data, _to_json_safe
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def _dimension_applies_to_sources(
    column: str,
    data_context: dict,
    widget_sources: list[str],
) -> bool:
    """Check if a filter dimension applies to the given widget sources."""
    dimensions = data_context.get("dimensions", {})
    # Find the dimension by column name
    for dim_name, dim_data in dimensions.items():
        if dim_data.get("column") == column:
            dim_sources = dim_data.get("sources", [])
            # Check if any of the widget's sources overlap with the dimension's sources
            return bool(set(dim_sources) & set(widget_sources))
    # Context provided but column not found → filter doesn't apply to this widget.
    # Only fall back to True when no data_context at all (backward compat).
    return data_context is None


_OP_MAP = {
    'eq': '=',
    'neq': '!=',
    'gt': '>',
    'gte': '>=',
    'lt': '<',
    'lte': '<=',
    'ilike': 'ILIKE',
}


def _resolve_inject_dialect(connection) -> str:
    """sqlglot dialect for filter injection, matching the engine that runs the SQL.

    Dataset / bigquery_ga4 connections are DataPlane-backed; their stored SQL
    dialect tracks settings.disable_local_data_plane (BigQuery in lockdown,
    DuckDB in dev) — mirror that so the injected WHERE parses + binds correctly.
    Passing the raw db_type (e.g. 'dataset') makes sqlglot raise 'Unknown dialect'
    and fall back to a naive subquery wrap that mis-scopes the filter.
    """
    db_type = (getattr(connection, "db_type", "") or "bigquery").lower()
    if db_type in ("dataset", "bigquery_ga4"):
        from backend.config import settings
        return "bigquery" if getattr(settings, "disable_local_data_plane", False) else "duckdb"
    return {"postgres": "postgres", "postgresql": "postgres",
            "mysql": "mysql", "bigquery": "bigquery"}.get(db_type, db_type)

# psycopg2-style placeholders (`%(name)s`) aren't valid SQL, so sqlglot can't
# parse them as expressions. We build conditions via the AST instead, using
# `exp.Placeholder` (which sqlglot renders dialect-aware: `@name` for BigQuery,
# `:name` elsewhere). After rendering we swap to `%(name)s`. Param keys are
# namespaced with `_f` to avoid colliding with any real `@name` / `:name`
# token in user SQL.
import re as _re
_PLACEHOLDER_REWRITE = _re.compile(r"[@:](_f\d+(?:_\d+)?)\b")
_ISO_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _lookup_column_type(data_context: dict | None, column: str) -> str | None:
    """Return UPPERCASE column type from data_context, or None if unknown.

    Date-pickers send `YYYY-MM-DD` strings that BigQuery binds as DATE. When the
    actual column is TIMESTAMP/DATETIME, BQ refuses the comparison (no implicit
    DATE→TIMESTAMP coerce in operators). `_build_ast_condition` uses this to
    decide whether to wrap the placeholder in a CAST.

    Dashboard contexts expose types under `dimensions[name].type`; connection
    contexts use `tables[name].columns[col].type`. Both shapes are checked.
    """
    if not data_context:
        return None
    dim = (data_context.get("dimensions") or {}).get(column)
    if isinstance(dim, dict) and dim.get("type"):
        return str(dim["type"]).upper()
    for tbl in (data_context.get("tables") or {}).values():
        cols = (tbl or {}).get("columns") or {}
        meta = cols.get(column)
        if isinstance(meta, dict) and meta.get("type"):
            return str(meta["type"]).upper()
    return None


def inject_filters(
    sql: str,
    filters: List[FilterParam],
    data_context: dict | None = None,
    widget_sources: list[str] | None = None,
    dialect: str = "bigquery",
) -> Tuple[str, dict]:
    """
    Inject filter conditions into widget SQL using sqlglot's AST.

    The injector picks the innermost SELECT scope whose real-table sources cover
    every filter column (push-down before aggregation). If no scope covers all
    columns, the outermost SELECT is used (post-aggregation filter on widget
    output). Calendar-bounds CTEs and similar FROM-less scopes are skipped
    automatically because their `scope.sources` are empty.

    *dialect* selects how both the SQL is parsed/rendered and how the value
    placeholders are emitted:
      - "bigquery" (default): psycopg2 `%(key)s` placeholders (source-DB path).
      - "duckdb":   DuckDB `$key` named placeholders (DataPlane serving path,
        bound positionally-by-name from the params dict).
    The returned params dict keys match the placeholder names (sans sigil) in
    both cases. Column names are emitted as quoted identifiers so reserved words
    and mixed-case names round-trip safely.

    If parsing fails (malformed SQL), falls back to a subquery wrap:
    `SELECT * FROM (<sql>) AS _wf WHERE ...`, placeholders still dialect-correct.
    """
    if not filters:
        return sql, {}

    if data_context and widget_sources:
        filters = [
            f for f in filters
            if _dimension_applies_to_sources(f.column, data_context, widget_sources)
        ]
        if not filters:
            return sql, {}

    sql = sql.rstrip().rstrip(';').rstrip()

    params: dict = {}
    ast_conditions: list = []
    for i, f in enumerate(filters):
        cond, sub_params = _build_ast_condition(i, f, data_context)
        ast_conditions.append(cond)
        params.update(sub_params)

    try:
        modified = _inject_via_sqlglot(sql, filters, ast_conditions, data_context, dialect)
    except Exception as e:
        logger.warning(
            "inject_filters: sqlglot rewrite failed (%s); falling back to subquery wrap",
            e,
        )
        modified = _wrap_subquery_fallback(sql, params, filters, dialect)

    return modified, params


_DATE_LIKE_TYPES = ("TIMESTAMP", "DATETIME", "DATE")


def _build_ast_condition(i: int, f: FilterParam, data_context: dict | None = None):
    """Return (sqlglot AST condition, param dict) for one FilterParam.

    Date-pickers send `YYYY-MM-DD` strings that the BQ data plane binds as DATE.
    When the filter column is any date-like type (TIMESTAMP / DATETIME / DATE)
    the column is wrapped in `DATE(...)` so the comparison is `DATE >= DATE`
    regardless of the underlying column type. This is more robust than casting
    the placeholder, because `data_context` types can drift from the actual
    BigQuery schema (pandas-naive timestamps land as BQ DATETIME but the
    context can label them TIMESTAMP).
    """
    from sqlglot import exp

    col_type = _lookup_column_type(data_context, f.column)
    is_date_like = (
        isinstance(f.value, str)
        and bool(_ISO_DATE_RE.match(f.value))
        and col_type is not None
        and any(t in col_type for t in _DATE_LIKE_TYPES)
    )

    raw_col = exp.column(f.column, quoted=True)
    col = exp.func("DATE", raw_col) if is_date_like else raw_col

    if f.op == 'in':
        values = f.value if isinstance(f.value, list) else [f.value]
        param_keys = [f'_f{i}_{j}' for j in range(len(values))]
        cond = exp.In(
            this=col,
            expressions=[exp.Placeholder(this=k) for k in param_keys],
        )
        return cond, {k: v for k, v in zip(param_keys, values)}

    pk = f'_f{i}'
    op_to_exp = {
        'eq': exp.EQ, 'neq': exp.NEQ,
        'gt': exp.GT, 'gte': exp.GTE,
        'lt': exp.LT, 'lte': exp.LTE,
        'ilike': exp.ILike,
    }
    # ILIKE only binds to text. A search control on a numeric column (e.g.
    # item_code BIGINT) would otherwise raise a DuckDB binder error
    # (~~*(BIGINT, STRING_LITERAL)) → the widget serve fails and falls back.
    # Cast to text so ILIKE is valid regardless of column type (no-op for text).
    this_col = exp.cast(col, to="TEXT") if f.op == 'ilike' else col
    cond = op_to_exp[f.op](this=this_col, expression=exp.Placeholder(this=pk))
    return cond, {pk: f.value}


def _inject_via_sqlglot(
    sql: str,
    filters: List[FilterParam],
    conditions: list,
    data_context: dict | None,
    dialect: str = "bigquery",
) -> str:
    """Parse *sql* in *dialect*, pick the best SELECT scope, attach WHERE there.

    Raises on parse failure so the caller can route to the subquery-wrap fallback.
    """
    import sqlglot
    from sqlglot import exp
    from sqlglot.optimizer.scope import build_scope

    ast = sqlglot.parse_one(sql, dialect=dialect)
    root_scope = build_scope(ast)
    if root_scope is None:
        raise ValueError("no SELECT scope")

    candidate_scopes = []
    for scope in root_scope.traverse():
        real_tables = [
            src for src in scope.sources.values()
            if isinstance(src, exp.Table)
        ]
        if real_tables:
            candidate_scopes.append((scope, real_tables))

    filter_columns = {f.column for f in filters}
    target_scope = _pick_target_scope(candidate_scopes, filter_columns, data_context)
    if target_scope is None:
        # No inner scope covers all filter columns. Appending to root_scope risks
        # referencing columns that aren't in the outer projection (BigQuery 400).
        # Raise so inject_filters routes to the subquery-wrap fallback instead.
        raise ValueError("no covering scope for filter columns — routing to subquery wrap")

    target_select = target_scope.expression
    if not isinstance(target_select, exp.Select):
        raise ValueError(f"target scope is not a SELECT: {type(target_select).__name__}")

    # A filter column that is an equi-join key (present on BOTH sides of a
    # `JOIN ... ON a.x = b.x`) exists in 2+ tables, so an unqualified reference to
    # it raises "ambiguous reference". Qualify those to the actual join-side alias
    # (either side is equivalent for an equi-join). Non-join columns resolve
    # unambiguously and are left untouched.
    join_key_alias: dict[str, str] = {}
    for eq in target_select.find_all(exp.EQ):
        lhs, rhs = eq.this, eq.expression
        if (isinstance(lhs, exp.Column) and isinstance(rhs, exp.Column)
                and lhs.table and rhs.table
                and lhs.name.lower() == rhs.name.lower()):
            join_key_alias[lhs.name.lower()] = lhs.table
    if join_key_alias:
        for cond in conditions:
            for colnode in cond.find_all(exp.Column):
                if not colnode.table:
                    alias = join_key_alias.get(colnode.name.lower())
                    if alias:
                        colnode.set("table", exp.to_identifier(alias))

    for cond in conditions:
        target_select.where(cond, append=True, copy=False)

    rendered = ast.sql(dialect=dialect)
    if dialect == "duckdb":
        # DuckDB renders exp.Placeholder as `$name` natively — bound by name from
        # the params dict, no rewrite needed.
        return rendered
    # BigQuery renders exp.Placeholder as `@name`; MySQL/Postgres render `:name`.
    # Both swap to the psycopg2 / pymysql `%(name)s` form the source-DB connectors bind.
    return _PLACEHOLDER_REWRITE.sub(r"%(\1)s", rendered)


def _pick_target_scope(
    candidate_scopes: list,
    filter_columns: set[str],
    data_context: dict | None,
):
    """Pick the innermost scope whose real tables collectively cover every filter column.

    Coverage is judged via *data_context.tables[table].columns* when available
    (the same dict the dashboard agent consumes). If no context is provided,
    falls back to "innermost scope that has any real table" — good enough for
    the bounds-CTE case and won't worsen behaviour for simple queries.
    """
    if not candidate_scopes:
        return None

    # Innermost first: scope.traverse() yields parents before children, so reverse.
    ordered = list(reversed(candidate_scopes))

    tables_meta = (data_context or {}).get("tables") or {}

    def covers(real_tables) -> bool:
        if not tables_meta:
            return True  # no context → assume innermost real-table scope is correct
        available_cols: set[str] = set()
        for tbl in real_tables:
            tbl_name = tbl.name
            cols = ((tables_meta.get(tbl_name) or {}).get("columns") or {})
            available_cols.update(cols.keys())
        return filter_columns.issubset(available_cols)

    for scope, real_tables in ordered:
        if covers(real_tables):
            return scope
    return None


def _wrap_subquery_fallback(
    sql: str,
    params: dict,
    filters: List[FilterParam],
    dialect: str = "bigquery",
) -> str:
    """Fallback when sqlglot can't parse the SQL.

    Wraps the original query as a subquery and applies the WHERE on top. The
    filter column must survive into the subquery's output for this to work; for
    widgets that's normally true because filter columns are dimensions and
    dashboards project their dimensions. Placeholders follow *dialect*:
    `$key` for DuckDB, `%(key)s` otherwise.
    """
    def _ph(key: str) -> str:
        return f"${key}" if dialect == "duckdb" else f"%({key})s"

    conditions: list[str] = []
    for i, f in enumerate(filters):
        col = f'"{f.column}"'
        if f.op == 'in':
            values = f.value if isinstance(f.value, list) else [f.value]
            placeholders = [_ph(f'_f{i}_{j}') for j in range(len(values))]
            conditions.append(f'{col} IN ({", ".join(placeholders)})')
        else:
            op = _OP_MAP[f.op]
            conditions.append(f'{col} {op} {_ph(f"_f{i}")}')
    condition_clause = ' AND '.join(conditions)
    return f"SELECT * FROM (\n{sql}\n) AS _wf WHERE {condition_clause}"

#: "no plane argument", as distinct from "resolved, and there is none". Local to
#: this module rather than imported from dashboard_cache: every reference to that
#: module here is a function-level import (circular-import convention), and an
#: unset value is forwarded by *omitting* the kwarg, so the two sentinels never
#: need to be the same object.
_UNSET = object()


def _resolve_serving_plane(org_id: str | None, user_id: str, db: Session):
    """Resolve the DataPlane backing the `_dash_*` widget cache once per request.

    Returns the plane, or None when none is provisioned / resolution fails — callers
    treat None as a cold cache and fall back to the source connector, which is what
    a raised `NoPlaneProvisionedError` produced before this was hoisted.

    Hoisted for connection accounting, not speed. `read_widget_data_plane` resolves
    with no session, opening a *second* pooled connection while this request's own
    `db` is still checked out; per widget that put 2-3 connections in flight per
    request against a pool of 10 (`DB_POOL_SIZE`+`DB_MAX_OVERFLOW`), and a
    multi-widget dashboard load exhausted it — `QueuePool limit ... timed out`.
    Passing `db` here reuses the connection the request already holds.

    Same shape as `agents/dashboard_tools._resolve_widget_connections`, which fixed
    this exact per-widget pattern on the dashboard-*creation* path in v0.3.2; the
    serve path kept the original.
    """
    from backend.services.dashboard_cache import widget_plane_scope
    from backend.services.data_plane_service import get_default_plane

    try:
        return get_default_plane(widget_plane_scope(org_id, user_id), db)
    except Exception:
        logger.debug("DataPlane resolution failed; serving from source", exc_info=True)
        return None


def _read_widget_from_cache(
    dashboard_id: int,
    widget_id: str,
    org_id: str | None = None,
    user_id: str | None = None,
    plane=_UNSET,
) -> "QueryResult | None":
    """Read widget data from the DataPlane Parquet cache.

    Returns a QueryResult on hit, or None when the table doesn't exist yet
    (cold cache → caller should fall back to the source connector).

    `plane` is the request-scoped plane from `_resolve_serving_plane`. Omitted, the
    read resolves its own (and pays its own connection); passed as None it means
    resolution already failed, so the read reports a cold cache without retrying —
    see `_UNSET`.
    """
    import time
    from backend.connectors.base import QueryResult
    from backend.services.dashboard_cache import read_widget_data_plane

    start = time.time()
    # Unset → omit the kwarg so dashboard_cache applies its own default (resolve
    # here). Passing plane=None explicitly means "already resolved, none found".
    plane_kw = {} if plane is _UNSET else {"plane": plane}
    dp_data = read_widget_data_plane(dashboard_id, widget_id, org_id, user_id or "", **plane_kw)
    if dp_data is None:
        return None
    return QueryResult(
        columns=dp_data["columns"],
        rows=dp_data["rows"],
        row_count=dp_data["row_count"],
        execution_time_ms=(time.time() - start) * 1000,
    )


def _duckdb_serving_enabled(org_id: str | None) -> bool:
    """True when the per-Org `duckdb_widget_serving` flag is on for this Org."""
    if not org_id:
        return False
    from backend.config.feature_flags import enabled
    return enabled(str(org_id), "duckdb_widget_serving")


def _widget_cache_enabled(org_id: str | None) -> bool:
    """True when the per-Org `widget_result_cache` flag is on for this Org."""
    if not org_id:
        return False
    try:
        from backend.config.feature_flags import enabled
        return enabled(str(org_id), "widget_result_cache")
    except Exception:
        logger.debug("widget_result_cache flag check failed", exc_info=True)
        return False


def _widget_cache_key(dashboard_id, widget_id, connection_id, sql, filters, org_id, user_id):
    """(key, ttl) for this widget read, or (None, None) when caching doesn't
    apply (no dashboard/widget identity, or the per-Org flag is off).

    Editor/preview calls carry no widget_id, so they are naturally uncached.
    """
    if not dashboard_id or not widget_id or not _widget_cache_enabled(org_id):
        return None, None
    from backend.config import settings
    from backend.services import widget_result_cache as wrc

    scope_kind, scope_id = ("org", org_id) if org_id else ("user", user_id)
    filters_dump = [
        f.model_dump() if hasattr(f, "model_dump") else dict(f)
        for f in (filters or [])
    ]
    generation = wrc.get_generation(dashboard_id)
    key = wrc.build_key(scope_kind, scope_id, dashboard_id, widget_id, connection_id, sql, filters_dump, generation)
    ttl = settings.widget_cache_ttl_filtered if filters else settings.widget_cache_ttl_unfiltered
    return key, ttl


def _widget_cache_lookup(key, mapping) -> "WidgetRefreshResponse | None":
    """Cache hit → WidgetRefreshResponse replaying stored rows through the
    current mapping (mapping can change without the SQL changing). None on miss."""
    if not key:
        return None
    from types import SimpleNamespace
    from backend.services import widget_result_cache as wrc

    hit = wrc.get(key)
    if hit is None:
        return None
    try:
        result = SimpleNamespace(
            columns=hit["columns"],
            rows=hit["rows"],
            row_count=hit.get("row_count", len(hit["rows"])),
            execution_time_ms=0.0,
            truncated=hit.get("truncated", False),
        )
        config = transform_widget_data(result, mapping)
    except Exception:
        logger.debug("widget_result_cache replay failed; treating as miss", exc_info=True)
        return None
    return WidgetRefreshResponse(
        config=config,
        execution_time_ms=0.0,
        row_count=result.row_count,
        truncated=result.truncated,
        refreshed_at=hit.get("cached_at") or datetime.now(timezone.utc).isoformat(),
        source_columns=result.columns,
        source_rows=result.rows,
        served_from=hit.get("served_from"),
    )


def _widget_cache_store(key, ttl, resp: "WidgetRefreshResponse | None") -> None:
    """Write-through from a refresh response. `put` stores data_plane / cache
    outcomes for the caller TTL, and source-fallback results too but with a short
    clamped TTL (`widget_cache_ttl_source`) so repeat opens are fast without
    pinning stale source data."""
    if not key or resp is None:
        return
    from backend.services import widget_result_cache as wrc

    wrc.put(
        key,
        {
            "columns": resp.source_columns,
            "rows": resp.source_rows,
            "row_count": resp.row_count,
            "truncated": resp.truncated,
            "served_from": resp.served_from,
            "cached_at": resp.refreshed_at,
        },
        ttl=ttl,
    )


def _serving_org_and_shared(dashboard, current_user):
    """Return (serving_org_id, is_shared) for widget serving.

    Shared (cross-org) dashboards serve from the HOST org's DataPlane/cache, so
    the serving org is the dashboard's org, not the viewer's home org. `is_shared`
    is anchored to the viewer's HOME org (matching dashboards.py) so it stays
    stable regardless of any active-workspace header.
    """
    dash_org = str(dashboard.org_id) if getattr(dashboard, "org_id", None) else None
    user_org = getattr(current_user, "home_org_id", None) or (
        str(current_user.org_id) if getattr(current_user, "org_id", None) else None
    )
    is_shared = bool(dash_org and user_org and dash_org != str(user_org))
    serving_org = dash_org or (str(user_org) if user_org else None)
    return serving_org, is_shared


def _readable_connection(db, connection_id, current_user, dashboard):
    """Resolve the DatabaseConnection for serving a (possibly shared) dashboard.

    Own dashboards: caller must own the connection (unchanged).
    Shared (cross-org) dashboards: the connection must belong to a user in the
    dashboard's (host) org — read-only serving from host parquet only.
    """
    from backend.services.seed import shared_sample_clause
    _, is_shared = _serving_org_and_shared(dashboard, current_user) if dashboard else (None, False)
    q = db.query(DatabaseConnection).filter(DatabaseConnection.id == connection_id)
    if is_shared:
        connection = (
            q.join(User, DatabaseConnection.user_id == User.id)
            .filter(User.org_id == str(dashboard.org_id))
            .first()
        )
    else:
        connection = q.filter(DatabaseConnection.user_id == current_user.id).first()
    if connection is not None:
        return connection
    # Shared read-only sample: readable by any user, independent of dashboard.
    # Checked only on ownership miss so the common case stays one query.
    return q.filter(shared_sample_clause()).first()


def _shared_serve_ctx(is_shared: bool, serving_org):
    """Context manager wrapping DataPlane reads for SHARED-dashboard serving.

    The governance DataPlane middleware enforces per-table grants against the
    request user. A viewer's access to a shared dashboard is governed by the
    share (org membership), not per-table grants, so its plane reads run under a
    system_context — ACL-bypassed and audited as a system actor. No-op for own
    dashboards (the viewer already holds grants in their home org).
    """
    from contextlib import nullcontext
    if not (is_shared and serving_org):
        return nullcontext()
    from backend.auth.system_context import system_context
    from backend.data_plane.scope import OwnerScope
    return system_context(
        reason="shared_dashboard.serve", scope=OwnerScope("org", str(serving_org))
    )


def _build_widget_response(result, mapping, served_from: str = "data_plane") -> "WidgetRefreshResponse":
    """Shared QueryResult → WidgetRefreshResponse (local + GCS serving paths).

    Both callers today are DuckDB-over-Parquet (LocalFilesystemDataPlane and
    GCSDuckDBReader), so the default `served_from="data_plane"` fits. The legacy
    cache-read path and the source-DB fallback set their own value explicitly.
    """
    return WidgetRefreshResponse(
        config=transform_widget_data(result, mapping),
        execution_time_ms=result.execution_time_ms,
        row_count=result.row_count,
        truncated=result.truncated,
        refreshed_at=datetime.now(timezone.utc).isoformat(),
        source_columns=result.columns,
        source_rows=[[_to_json_safe(v) for v in row] for row in result.rows],
        served_from=served_from,
    )


def _plane_missing_after_first_ingest(connection, tables: list[str], db: Session) -> bool:
    """Has any pipeline backing `connection` + `tables` already completed its
    bootstrap ingest? If yes, missing Parquet is an operational error rather
    than a "not warmed yet" condition — callers should 503 instead of silently
    falling through to the source DB (the not-ready policy from the plan).

    Returns False when no pipeline rows exist (CSV / non-SQL connectors that
    aren't tracked here) so legacy behavior is preserved.
    """
    if not tables:
        return False
    try:
        from backend.models.pipeline import Pipeline
        rows = (
            db.query(Pipeline)
            .filter(Pipeline.source_connection_id == connection.id)
            .all()
        )
    except Exception:
        return False
    if not rows:
        return False
    table_set = {t.lower() for t in tables}
    for p in rows:
        # `target_table` is the prefixed plane-side name; `extraction_config.tables`
        # carries the source-side name(s). Match either to be liberal.
        names: set[str] = set()
        if p.target_table:
            names.add(p.target_table.lower())
        for src in (p.extraction_config or {}).get("tables", []) or []:
            names.add(str(src).lower())
        if names & table_set and bool(getattr(p, "first_ingest_done", False)):
            return True
    return False


def _serve_widget_via_dataplane(
    request: "WidgetRefreshRequest",
    dashboard: "Dashboard | None",
    current_user: User,
    db: Session,
    reader=None,
) -> "WidgetRefreshResponse | None":
    """Serve a widget read from DuckDB over the DataPlane Parquet.

    Per-plane behavior:
      - **LocalFilesystemDataPlane (dev):** run the widget's (DuckDB) SQL live
        over the local source-table views — filtered and unfiltered alike.
      - **BigQueryGCSPlane (prod):** DuckDB-over-GCS via httpfs (Phase 2).
        Unfiltered → read the warm `_dash_*` results cache (small, fast);
        filtered → run the full SQL live (dt=-pruned). Gated by the reader
        factory (residency-locked / customer / no-HMAC planes → None → BQ).

    When *reader* is supplied (bulk refresh passing one shared `GCSDuckDBReader`
    for the whole dashboard), the prod GCS branch reuses it and does NOT close
    it — the caller owns its lifecycle. When *reader* is None, the branch
    creates and closes its own per call (single-widget path, unchanged).

    Returns a response on success, or None to fall back to the legacy cache /
    source-DB path. Transpile never runs here — stored SQL is assumed DuckDB;
    unmigrated BigQuery SQL fails to parse → fall back, nothing breaks.
    """
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
    from backend.services.data_plane_service import (
        get_gcs_duckdb_reader,
        get_plane_for_connection,
        plane_table_map,
    )
    from backend.utils.sql_refs import extract_table_refs, rewrite_table_refs

    connection = _readable_connection(db, request.connection_id, current_user, dashboard)
    if not connection:
        return None

    # GAP-10 cutover gate: only dashboards journaled as DuckDB (migrated or
    # born-DuckDB) serve via DuckDB; un-migrated ones fall back to BQ/source so
    # a mid-cutover viewer never gets BigQuery SQL run through DuckDB.
    from backend.migration.dialect_migration import is_duckdb_ready
    if not is_duckdb_ready(request.dashboard_id, db):
        return None

    data_context = dashboard.data_context if dashboard else None

    # Same (plane, scope) the writers (CSV connector, Pipeline, migration) use —
    # guarantees the read resolves to where the source Parquet was written.
    plane, scope = get_plane_for_connection(connection)

    # Widget SQL is written against source table names (e.g. `orders`); rewrite
    # them to the Pipeline's materialized plane table (e.g. `acme__orders`) so
    # the Parquet glob resolves. No-op when the connection has no pipelines.
    from backend.utils.sql_refs import qualifier_allowlist
    base_sql, _ = rewrite_table_refs(
        request.sql, plane_table_map(connection, db), qualifier_allowlist(connection)
    )
    # DuckDB reads the same ANSI quoting the agent writes, so this only quotes
    # reserved-word identifiers (a column literally named `left`, `order`, `end`).
    base_sql = normalize_sql_for(base_sql, "duckdb")

    # ── Dev: local plane → serve live over local Parquet ──────────────────
    if isinstance(plane, LocalFilesystemDataPlane):
        tables = extract_table_refs(base_sql)
        if not tables or not all(plane.table_exists(scope, t) for t in tables):
            # Cold/missing source. Apply the bootstrap-fallback policy: allow
            # one live source query while the connection's pipelines are still
            # pre-first-ingest; once any matching pipeline has
            # `first_ingest_done=True`, refuse to re-hammer the source DB.
            if _plane_missing_after_first_ingest(connection, tables, db):
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "plane_table_missing",
                        "message": (
                            "DataPlane Parquet for this widget is missing after the "
                            "first ingest completed. Trigger a manual sync to repopulate."
                        ),
                    },
                )
            return None  # bootstrap fallback: legacy path hits source DB
        sql, params = base_sql, None
        if request.filters:
            sql, params = inject_filters(
                base_sql, request.filters,
                data_context=data_context, widget_sources=request.widget_sources,
                dialect="duckdb",
            )
        return _build_widget_response(plane.query(scope, sql, params), request.mapping)

    # ── Prod: DuckDB-over-GCS (direct httpfs) ─────────────────────────────
    owns_reader = reader is None
    try:
        if reader is None:
            reader = get_gcs_duckdb_reader(scope, db)
        if reader is None:
            return None  # residency-locked / customer / no-HMAC → BQ fallback

        if request.filters:
            # Filtered → no unfiltered cache hit; run the full SQL live (pruned).
            sql, params = inject_filters(
                base_sql, request.filters,
                data_context=data_context, widget_sources=request.widget_sources,
                dialect="duckdb",
            )
            return _build_widget_response(reader.query(scope, sql, params), request.mapping)

        # Unfiltered → prefer the warm _dash_* results cache (small, fast); if
        # it's cold or mis-scoped, serve live over the source Parquet (same as
        # the dev local-plane branch) so the widget still reads from the lake.
        if dashboard and request.widget_id:
            from backend.services.dashboard_cache import _sanitize_widget_id
            cache_table = f'_dash_{request.dashboard_id}__{_sanitize_widget_id(request.widget_id)}'
            try:
                result = reader.query(scope, f'SELECT * FROM "{cache_table}"')
                return _build_widget_response(result, request.mapping)
            except Exception as e:
                # Cold/missing warm cache is the common, expected case → fall
                # through to the live read below. Logged at debug (not warning)
                # so a genuine error (bad SQL, permissions) is still observable
                # when troubleshooting without spamming the common cold path.
                logger.debug(
                    "Warm _dash_ cache miss for widget %s (table %s): %s — serving live",
                    request.widget_id, cache_table, e,
                )
        return _build_widget_response(reader.query(scope, base_sql), request.mapping)
    except Exception as e:
        logger.warning(
            "DuckDB-over-GCS serve failed for widget %s, falling back: %s",
            request.widget_id, e,
        )
        return None
    finally:
        if owns_reader and reader is not None:
            reader.close()


def _plane_miss_key(connection_id, sql: str) -> tuple:
    """Key for the request-scoped "this won't serve from the plane" memo.

    A missing Parquet glob costs a full GCS round-trip (~3-4s) to discover, and
    every widget on the same tables rediscovers it. Same connection + same table
    set → same outcome, so probe once. Widgets on other tables still get theirs.
    """
    from backend.utils.sql_refs import extract_table_refs
    tables = extract_table_refs(sql or "")  # sorted + deduped; [] on parse failure
    return (connection_id, tuple(tables)) if tables else (connection_id, sql)


router = APIRouter(prefix="/dashboards", tags=["widget-data"])


@router.post("/widgets/refresh", response_model=WidgetRefreshResponse)
async def refresh_widget(
    request: WidgetRefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-execute a SQL query and transform the result into widget config data.

    The caller supplies connection_id, sql, and mapping. The response contains
    the new config dict to merge into widget.widget.config plus metadata.

    With `duckdb_widget_serving` on, every read (filtered or not) is served from
    DuckDB over the DataPlane source Parquet; cold sources fall back. With the
    flag off, behavior is unchanged: the Parquet `_dash_*` cache serves
    unfiltered reads and the source DB serves the rest.

    The serving ladder is entirely synchronous (DuckDB-over-GCS scans, Parquet
    cache reads, source-DB connectors) — running it on the event loop starved
    /health and got pods liveness-killed (2026-07-23 incident), so it runs in
    a worker thread.
    """
    return await asyncio.to_thread(_refresh_widget_sync, request, current_user, db)


def _refresh_widget_sync(
    request: WidgetRefreshRequest,
    current_user: User,
    db: Session,
):
    dashboard = None
    if request.dashboard_id:
        # Org-wide visibility, matching GET /dashboards/{id}: any org member who
        # can view the dashboard can refresh its widgets.
        from backend.api.dashboards import _dashboard_visible_to
        dashboard = (
            _dashboard_visible_to(db.query(Dashboard), current_user, db)
            .filter(Dashboard.id == request.dashboard_id)
            .first()
        )

    serving_org, dash_is_shared = (
        _serving_org_and_shared(dashboard, current_user) if dashboard else (None, False)
    )
    org_id = serving_org or getattr(current_user, "org_id", None)

    # Redis result cache (flag-gated, per-Org). Keys embed the dashboard's
    # materialization generation, so unfiltered hits are exact; hits skip the
    # serving ladder entirely.
    cache_key, cache_ttl = (None, None)
    if dashboard:
        cache_key, cache_ttl = _widget_cache_key(
            request.dashboard_id, request.widget_id, request.connection_id,
            request.sql, request.filters, org_id, current_user.id,
        )
        cached_resp = _widget_cache_lookup(cache_key, request.mapping)
        if cached_resp is not None:
            return cached_resp

    # DuckDB-over-DataPlane serving (flag-gated, per-Org). Serves filtered and
    # unfiltered reads alike; returns None to fall through on cold source etc.
    if dashboard and _duckdb_serving_enabled(org_id):
        try:
            with _shared_serve_ctx(dash_is_shared, serving_org):
                served = _serve_widget_via_dataplane(request, dashboard, current_user, db)
            if served is not None:
                _widget_cache_store(cache_key, cache_ttl, served)
                return served
        except Exception as e:
            logger.warning(
                "DuckDB serving failed for widget %s, falling back to source DB: %s",
                request.widget_id, e,
            )

    # DataPlane cache read — only when no filters (Parquet has no WHERE injection).
    if dashboard and request.widget_id and not request.filters:
        try:
            # Resolved with this request's session. Already inside the unfiltered
            # branch, so it is only paid when the cache is actually read. None means
            # no plane — the read reports a cold cache and the source fallback below
            # runs, same outcome as the raise this replaced.
            plane = _resolve_serving_plane(serving_org, current_user.id, db)
            with _shared_serve_ctx(dash_is_shared, serving_org):
                result = _read_widget_from_cache(
                    request.dashboard_id,
                    request.widget_id,
                    org_id=serving_org,
                    user_id=current_user.id,
                    plane=plane,
                )
            if result is not None:
                config = transform_widget_data(result, request.mapping)
                resp = WidgetRefreshResponse(
                    config=config,
                    execution_time_ms=result.execution_time_ms,
                    row_count=result.row_count,
                    truncated=False,
                    refreshed_at=datetime.now(timezone.utc).isoformat(),
                    source_columns=result.columns,
                    source_rows=[
                        [_to_json_safe(v) for v in row]
                        for row in result.rows
                    ],
                    served_from="cache",
                )
                _widget_cache_store(cache_key, cache_ttl, resp)
                return resp
        except Exception as e:
            logger.warning(f"DataPlane cache read failed for widget {request.widget_id}, falling back to source DB: {e}")

    # Fallback: source DB query. Shared (cross-org) dashboards read live from the
    # HOST org's connection — `_readable_connection` authorizes a connection owned
    # by a user in the dashboard's org; own dashboards still require the caller to
    # own the connection.
    connection = _readable_connection(db, request.connection_id, current_user, dashboard)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    from backend.connectors.factory import get_connector_for_connection

    connector = get_connector_for_connection(connection, db)

    try:
        def _prepare(base_sql):
            """Inject filters into base_sql in the connection dialect."""
            if not request.filters:
                return base_sql, None
            data_context = dashboard.data_context if dashboard else None
            return inject_filters(
                base_sql, request.filters,
                data_context=data_context,
                widget_sources=request.widget_sources,
                dialect=_resolve_inject_dialect(connection),
            )

        # Route bigquery_ga4 widget SQL through the data plane (managed
        # materialised view) instead of the raw GA4 source connector.
        served_from = "source"
        if getattr(connector, "serves_from_plane", False) is True:
            # Migrated sqlite / CSV dataset: connector reads the DataPlane
            # (Parquet), not the origin database. Identity check — any
            # attribute-synthesising stand-in (MagicMock) must not opt in.
            served_from = "data_plane"
        if connection.db_type == "bigquery_ga4":
            sql, params = _prepare(request.sql)
            from backend.data_plane.scope import OwnerScope
            from backend.models.pipeline import Pipeline
            from backend.services.data_plane_service import get_default_plane
            _p = db.query(Pipeline).filter(
                Pipeline.source_connection_id == connection.id,
            ).first()
            if _p is not None:
                _scope = OwnerScope(kind=_p.owner_scope_kind, id=_p.owner_scope_id)
                _plane = get_default_plane(_scope, db)
                with _shared_serve_ctx(dash_is_shared, serving_org):
                    result = _plane.query(_scope, sql, params=params)
                served_from = "data_plane"
            else:
                result = connector.execute_query(sql, params=params)
        else:
            # Stored widget SQL is normally in the connection's native dialect
            # (agent-generated). Try it as-is with the filter first; fall back to
            # unfiltered (when the filter can't be applied — e.g. ambiguous column
            # in a joined query) and to a BigQuery→source transpile (legacy SQL).
            # Order ensures a native widget with a bad filter renders unfiltered
            # and never reaches transpile (which would corrupt native DATE_TRUNC).
            from backend.utils.sql_refs import transpile_to_engine
            db_type = (getattr(connection, "db_type", "") or "postgres").lower()
            target = {"postgres": "postgres", "postgresql": "postgres",
                      "mysql": "mysql", "bigquery": "bigquery",
                      "bigquery_ga4": "bigquery"}.get(db_type, db_type)

            # source: None = run as-is (native dialect); "bigquery" = legacy BQ
            # SQL; "postgres" = repair ANSI double-quoted identifiers ("col") to
            # the target's native quoting — the agent sometimes emits them and
            # they break on MySQL (see conn 50 / dash 36).
            # The native attempt runs normalized SQL: the agent emits ANSI
            # `"col"` whatever the surface is (a *string* on BigQuery) and leaves
            # reserved-word columns like `left` unquoted. The transpile plans
            # below can't repair either for dataset/plane connections — their
            # db_type isn't a sqlglot dialect, so `target` is invalid and every
            # non-native plan raises. No-op when the SQL is already correct.
            native_sql = normalize_sql_for(request.sql, _resolve_inject_dialect(connection))

            def _attempt(source, with_filter):
                base = (native_sql if source is None
                        else transpile_to_engine(request.sql, source=source, target=target))
                s, p = (_prepare(base) if with_filter else (base, None))
                return connector.execute_query(s, params=p)

            plans = [(None, True), (None, False), ("bigquery", True),
                     ("bigquery", False), ("postgres", True), ("postgres", False)]
            if not request.filters:
                plans = [(None, False), ("bigquery", False), ("postgres", False)]
            first_err = None
            for i, (tr, wf) in enumerate(plans):
                try:
                    if i:  # reset aborted-txn / stale conn before a retry
                        connector.close()
                    result = _attempt(tr, wf)
                    break
                except Exception as e:
                    first_err = first_err or e
            else:
                raise first_err

        config = transform_widget_data(result, request.mapping)

        resp = WidgetRefreshResponse(
            config=config,
            execution_time_ms=result.execution_time_ms,
            row_count=result.row_count,
            truncated=False,
            refreshed_at=datetime.now(timezone.utc).isoformat(),
            source_columns=result.columns,
            source_rows=[
                [_to_json_safe(v) for v in row]
                for row in result.rows
            ],
            served_from=served_from,
        )
        # Cache so reopening within the TTL is instant. `put` clamps the source
        # TTL short; no-op when the cache flag/key is off.
        _widget_cache_store(cache_key, cache_ttl, resp)
        return resp

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Widget refresh failed for connection {request.connection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")
    finally:
        connector.close()


async def render_widget_snapshots(dashboard, widget_ids, user, db) -> dict:
    """Render data configs for the given widget ids by reusing refresh_widget.

    Returns {str(widget_id): config} for the briefing snapshot — pays the live
    widget SQL once at generation time so the briefing view renders without it.
    Best-effort: a widget that lacks a dataSource or fails to render is skipped.
    """
    widgets_by_id = {str(w.get("id")): w for w in (dashboard.widgets or [])}
    out: dict = {}
    for wid in {str(w) for w in widget_ids if w}:
        w = widgets_by_id.get(wid)
        ds = (w or {}).get("dataSource") or {}
        connection_id, sql, mapping = ds.get("connectionId"), ds.get("sql"), ds.get("mapping")
        if not (connection_id and sql and mapping):
            continue
        # Mirror the frontend: fold the chart type into mapping so transforms match.
        chart_type = (w.get("widget") or {}).get("config", {}).get("type")
        if chart_type and "chartType" not in mapping:
            mapping = {**mapping, "chartType": chart_type}
        try:
            resp = await refresh_widget(
                WidgetRefreshRequest(
                    connection_id=connection_id, sql=sql, mapping=mapping,
                    filters=None, dashboard_id=dashboard.id, widget_id=wid,
                    widget_sources=w.get("sources"),
                ),
                current_user=user, db=db,
            )
            out[wid] = resp.config
        except Exception:
            logger.warning("Briefing snapshot render failed for widget %s", wid, exc_info=True)
    return out


@router.post("/{dashboard_id}/refresh", response_model=BulkRefreshResponse)
async def refresh_dashboard_widgets(
    dashboard_id: int,
    payload: Optional[BulkRefreshRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-execute SQL queries for all SQL-backed widgets in a dashboard.

    Each widget is read from the DataPlane Parquet cache when available;
    on cold cache the widget falls back to its source connector. Widgets
    without a dataSource are skipped; per-widget failures are captured as
    {error} rather than failing the entire request.

    Runs in a worker thread for the same reason `refresh_widget` does: the whole
    serving ladder is synchronous, and one dashboard's worth of it stalled the
    event loop for ~10s per filter change (`loop_watchdog` logged it), freezing
    every other request — the 2026-07-23 liveness-kill shape.
    """
    return await asyncio.to_thread(
        _refresh_dashboard_widgets_sync, dashboard_id, payload, current_user, db
    )


def _refresh_dashboard_widgets_sync(
    dashboard_id: int,
    payload: Optional[BulkRefreshRequest],
    current_user: User,
    db: Session,
) -> BulkRefreshResponse:
    # Org-wide visibility, matching GET /dashboards/{id}: any org member who
    # can view the dashboard can refresh its widgets.
    from backend.api.dashboards import _dashboard_visible_to
    dashboard = (
        _dashboard_visible_to(db.query(Dashboard), current_user, db)
        .filter(Dashboard.id == dashboard_id)
        .first()
    )

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    serving_org, dash_is_shared = _serving_org_and_shared(dashboard, current_user)

    widgets = dashboard.widgets or []
    results: dict = {}
    org_id = serving_org or getattr(current_user, "org_id", None)
    refreshed_at = datetime.now(timezone.utc).isoformat()
    # Dashboard-level filters (parity with single-widget refresh). When present,
    # the warm `_dash_*` cache is skipped (it holds unfiltered rows) and filters
    # are injected per widget on both the DuckDB and source-DB paths.
    filters = payload.filters if payload else None
    data_context = dashboard.data_context

    # One shared DuckDB-over-GCS reader for the whole dashboard, mirroring
    # materialize_dashboard: the connection cold-start (INSTALL/LOAD httpfs +
    # CREATE SECRET) and each table's view registration are paid once per
    # refresh instead of once per widget. The reader's bucket/creds resolve from
    # the Org's default plane, so one reader serves every (same-Org) widget;
    # the per-widget scope is still passed to `query()` for the glob path.
    # None when serving is off/unavailable (dev local plane, residency-locked,
    # customer-managed, no-HMAC) → `_serve_widget_via_dataplane` falls back
    # exactly as before (dev serves via its local-plane branch).
    duck_enabled = _duckdb_serving_enabled(org_id)
    shared_reader = None
    # Widgets pointing at the shared sample resolve to the Samples-org bucket, not
    # the viewer's org bucket — the shared reader is bound to the wrong bucket for
    # them. Serve those with a per-widget reader (reader=None) instead.
    sample_conn_ids: set = set()
    if duck_enabled:
        from backend.data_plane.scope import OwnerScope
        from backend.services.data_plane_service import get_gcs_duckdb_reader
        reader_scope = OwnerScope("org", org_id) if org_id else OwnerScope("user", current_user.id)
        shared_reader = get_gcs_duckdb_reader(reader_scope, db)

        from backend.services.seed import shared_sample_clause
        widget_conn_ids = [
            w.get("dataSource", {}).get("connectionId")
            for w in widgets if w.get("dataSource")
        ]
        widget_conn_ids = [cid for cid in widget_conn_ids if cid]
        if widget_conn_ids:
            sample_conn_ids = {
                r.id for r in db.query(DatabaseConnection.id).filter(
                    DatabaseConnection.id.in_(widget_conn_ids),
                    shared_sample_clause(),
                ).all()
            }

    # Source-DB fallback memoized per connection_id so widgets sharing a
    # connection don't each re-fetch the DatabaseConnection row and rebuild a
    # connector (the N+1 the old per-widget loop paid). Connectors are built
    # lazily on first fallback and closed once after the loop.
    connection_cache: dict = {}
    connector_cache: dict = {}

    # Request-scoped memo of (connection, tables) that already failed to serve
    # from the plane — see `_plane_miss_key`. Never leaks across requests.
    plane_miss_keys: set = set()

    # The `_dash_*` cache plane: resolved at most once for the whole dashboard, and
    # only if some widget actually reads the cache. Every widget here shares one
    # scope, so the per-widget resolution below was the same lookup N times, each
    # opening its own pooled connection on top of the one this request already
    # holds. Memoizing connection+connector (above) never covered this one.
    #
    # Lazy, not eager: a filtered request never touches `_dash_*` (filters skip the
    # cache — it holds unfiltered rows), and neither does one whose widgets all hit
    # the Redis result cache. Resolving up front would make those pay a lookup they
    # never use, and under lockdown a resolution miss invokes provision-on-miss —
    # a bucket/dataset side effect no request that skips the cache should trigger.
    cache_plane = _UNSET

    # Redis result cache (flag-gated, per-Org): generation, scope, and filter
    # canonicalization computed once for the whole dashboard; lookups are one
    # GET per widget. `bulk_cache_gen is not None` marks the cache active.
    bulk_cache_gen = None
    bulk_cache_scope = None
    bulk_cache_ttl = None
    bulk_filters_dump = None
    if _widget_cache_enabled(org_id):
        from backend.config import settings
        from backend.services import widget_result_cache as wrc
        bulk_cache_scope = ("org", org_id) if org_id else ("user", current_user.id)
        bulk_cache_gen = wrc.get_generation(dashboard_id)
        bulk_filters_dump = [
            f.model_dump() if hasattr(f, "model_dump") else dict(f)
            for f in (filters or [])
        ]
        bulk_cache_ttl = settings.widget_cache_ttl_filtered if filters else settings.widget_cache_ttl_unfiltered

    try:
        for widget in widgets:
            widget_id = widget.get("id")
            data_source = widget.get("dataSource")
            if not data_source:
                continue

            connection_id = data_source.get("connectionId")
            sql = data_source.get("sql")
            mapping = data_source.get("mapping")
            # Widgets JSONB may carry connectionId as a string; sample_conn_ids
            # holds DB ints, so normalize before the membership test below.
            try:
                connection_id = int(connection_id)
            except (TypeError, ValueError):
                pass

            if not connection_id or not sql or not mapping:
                results[widget_id] = {"error": "Incomplete dataSource (missing connectionId, sql, or mapping)"}
                continue

            chart_type = widget.get("widget", {}).get("config", {}).get("type")
            if chart_type and "chartType" not in mapping:
                mapping = {**mapping, "chartType": chart_type}

            # Redis result cache lookup — a hit skips the serving ladder.
            widget_cache_key = None
            if bulk_cache_gen is not None and widget_id:
                from backend.services import widget_result_cache as wrc
                widget_cache_key = wrc.build_key(
                    bulk_cache_scope[0], bulk_cache_scope[1], dashboard_id,
                    widget_id, connection_id, sql, bulk_filters_dump, bulk_cache_gen,
                )
                cached_resp = _widget_cache_lookup(widget_cache_key, mapping)
                if cached_resp is not None:
                    results[widget_id] = {
                        "config": cached_resp.config,
                        "refreshed_at": cached_resp.refreshed_at,
                        "served_from": cached_resp.served_from,
                    }
                    continue

            # DuckDB-over-DataPlane serving (flag-gated, per migrated dashboard) —
            # same path as single-widget refresh, so bulk loads on cut-over Orgs
            # avoid the per-widget BQ job. Falls through on None (GAP-7).
            miss_key = _plane_miss_key(connection_id, sql) if duck_enabled else None
            if miss_key is not None and miss_key not in plane_miss_keys:
                try:
                    with _shared_serve_ctx(dash_is_shared, serving_org):
                        served = _serve_widget_via_dataplane(
                            WidgetRefreshRequest(
                                connection_id=connection_id, sql=sql, mapping=mapping,
                                filters=filters, dashboard_id=dashboard_id, widget_id=widget_id,
                                widget_sources=widget.get("sources"),
                            ),
                            dashboard, current_user, db,
                            reader=(None if connection_id in sample_conn_ids else shared_reader),
                        )
                    if served is not None:
                        _widget_cache_store(widget_cache_key, bulk_cache_ttl, served)
                        results[widget_id] = {"config": served.config, "refreshed_at": refreshed_at, "served_from": served.served_from}
                        continue
                    plane_miss_keys.add(miss_key)
                except Exception as e:
                    plane_miss_keys.add(miss_key)
                    logger.warning(f"DuckDB serving failed for widget {widget_id}, falling back: {e}")

            # Try DataPlane cache — only when unfiltered (the `_dash_*` cache
            # holds unfiltered rows; serving it under a filter would be stale).
            if not filters:
                try:
                    # First widget to reach the cache resolves; the rest reuse it.
                    # `None` is a resolved result (no plane) and must not re-trigger.
                    if cache_plane is _UNSET:
                        cache_plane = _resolve_serving_plane(org_id, current_user.id, db)
                    with _shared_serve_ctx(dash_is_shared, serving_org):
                        cached = _read_widget_from_cache(
                            dashboard_id, widget_id,
                            org_id=org_id, user_id=current_user.id,
                            plane=cache_plane,
                        )
                    if cached is not None:
                        if widget_cache_key:
                            from backend.services import widget_result_cache as wrc
                            wrc.put(widget_cache_key, {
                                "columns": cached.columns,
                                "rows": [[_to_json_safe(v) for v in row] for row in cached.rows],
                                "row_count": cached.row_count,
                                "truncated": getattr(cached, "truncated", False),
                                "served_from": "cache",
                                "cached_at": refreshed_at,
                            }, ttl=bulk_cache_ttl)
                        results[widget_id] = {
                            "config": transform_widget_data(cached, mapping),
                            "refreshed_at": refreshed_at,
                            "served_from": "cache",
                        }
                        continue
                except Exception as e:
                    logger.warning(f"DataPlane cache read failed for widget {widget_id}, falling back to source DB: {e}")

            # Fallback: source DB query. Shared (cross-org) dashboards read live
            # from the HOST org's connection via `_readable_connection`. Connection
            # row + connector are memoized per connection_id so a dashboard with
            # many widgets on one connection pays a single fetch + connector build.
            if connection_id not in connection_cache:
                connection_cache[connection_id] = _readable_connection(
                    db, connection_id, current_user, dashboard
                )
            connection = connection_cache[connection_id]

            if not connection:
                results[widget_id] = {"error": f"Connection {connection_id} not found"}
                continue

            if connection_id not in connector_cache:
                from backend.connectors.factory import get_connector_for_connection
                connector_cache[connection_id] = get_connector_for_connection(connection, db)
            connector = connector_cache[connection_id]

            try:
                def _prepare_bulk(base_sql):
                    """Inject filters into base_sql in the connection dialect."""
                    if not filters:
                        return base_sql, None
                    return inject_filters(
                        base_sql, filters,
                        data_context=data_context,
                        widget_sources=widget.get("sources"),
                        dialect=_resolve_inject_dialect(connection),
                    )

                served_from = "source"
                if getattr(connector, "serves_from_plane", False) is True:
                    # Migrated sqlite / CSV dataset: connector reads the DataPlane.
                    served_from = "data_plane"
                if connection.db_type == "bigquery_ga4":
                    fb_sql, params = _prepare_bulk(sql)
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
                        with _shared_serve_ctx(dash_is_shared, serving_org):
                            result = _plane.query(_s, fb_sql, params=params)
                        served_from = "data_plane"
                    else:
                        result = connector.execute_query(fb_sql, params=params)
                else:
                    # Native-first with filter, then unfiltered, then BigQuery
                    # transpile (filtered/unfiltered). Order renders a native
                    # widget unfiltered when its filter is unusable and avoids
                    # corrupting native SQL via transpile. See refresh_widget.
                    from backend.utils.sql_refs import transpile_to_engine
                    db_type = (getattr(connection, "db_type", "") or "postgres").lower()
                    target = {"postgres": "postgres", "postgresql": "postgres",
                              "mysql": "mysql", "bigquery": "bigquery",
                              "bigquery_ga4": "bigquery"}.get(db_type, db_type)

                    # source: None = native as-is; "bigquery" = legacy BQ SQL;
                    # "postgres" = repair ANSI "col" identifiers to the target's
                    # native quoting (breaks on MySQL otherwise). See refresh_widget.
                    # Same normalization as refresh_widget's native attempt.
                    native_sql = normalize_sql_for(sql, _resolve_inject_dialect(connection))

                    def _attempt_bulk(source, with_filter):
                        base = (native_sql if source is None
                                else transpile_to_engine(sql, source=source, target=target))
                        s, p = (_prepare_bulk(base) if with_filter else (base, None))
                        return connector.execute_query(s, params=p)

                    plans = [(None, True), (None, False), ("bigquery", True),
                             ("bigquery", False), ("postgres", True), ("postgres", False)]
                    if not filters:
                        plans = [(None, False), ("bigquery", False), ("postgres", False)]
                    first_err = None
                    for _i, (_tr, _wf) in enumerate(plans):
                        try:
                            if _i:
                                connector.close()
                            result = _attempt_bulk(_tr, _wf)
                            break
                        except Exception as e:
                            first_err = first_err or e
                    else:
                        raise first_err
                # Cache the result so reopening this dashboard within the TTL is
                # instant instead of re-running live SQL. `put` clamps the source
                # TTL short (widget_cache_ttl_source); plane results keep the
                # caller TTL. No-op when the cache flag/key is off.
                if widget_cache_key:
                    from backend.services import widget_result_cache as wrc
                    wrc.put(widget_cache_key, {
                        "columns": result.columns,
                        "rows": [[_to_json_safe(v) for v in row] for row in result.rows],
                        "row_count": getattr(result, "row_count", len(result.rows)),
                        "truncated": getattr(result, "truncated", False),
                        "served_from": served_from,
                        "cached_at": refreshed_at,
                    }, ttl=bulk_cache_ttl)
                results[widget_id] = {
                    "config": transform_widget_data(result, mapping),
                    "refreshed_at": refreshed_at,
                    "served_from": served_from,
                }
            except Exception as e:
                logger.error(f"Bulk refresh failed for widget {widget_id}: {e}")
                results[widget_id] = {"error": str(e)}
    finally:
        if shared_reader is not None:
            shared_reader.close()
        for _connector in connector_cache.values():
            try:
                _connector.close()
            except Exception:
                pass

    return BulkRefreshResponse(widgets=results)


@router.post("/{dashboard_id}/materialize", status_code=202)
async def materialize_dashboard(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Trigger an immediate cache rebuild for a dashboard.

    Returns 202 Accepted with the Celery task ID.
    Rate limited to 1 request per dashboard per 5 minutes.
    """
    # Check dashboard exists and belongs to user
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    # Rate limit: max 1 per dashboard per 5 minutes
    import redis as _redis
    from backend.config import settings
    rate_limit_key = f"materialize_rate:{dashboard_id}"
    try:
        r = _redis.from_url(settings.redis_url)
        if r.exists(rate_limit_key):
            raise HTTPException(
                status_code=429,
                detail="Dashboard was recently materialized. Please wait 5 minutes between refreshes.",
            )
        r.setex(rate_limit_key, 300, "1")  # 5 min TTL
    except HTTPException:
        raise
    except Exception as redis_err:
        logger.warning(f"Redis rate limit check failed, proceeding: {redis_err}")

    from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
    task = execute_dashboard_refresh.delay(dashboard_id)

    return {"task_id": task.id, "message": "Materialization started"}


from backend.services.schema_utils import extract_table_names as _extract_table_names, build_schema_summary as _build_schema_summary


@router.post("/widgets/suggest-fix", response_model=WidgetSuggestFixResponse)
async def suggest_fix(
    request: WidgetSuggestFixRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Use the LLM to suggest a corrected SQL query based on the error message and schema.
    """
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == request.connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    from backend.services.schema_discovery import load_schema_file
    from backend.llm.factory import get_provider
    from backend.config import settings

    schema_summary = ""
    try:
        schema_json = load_schema_file(request.connection_id)
        referenced_tables = _extract_table_names(request.sql)
        schema_summary = _build_schema_summary(schema_json, referenced_tables)
    except FileNotFoundError:
        logger.warning(f"Schema file not found for connection {request.connection_id}, proceeding without schema")

    mapping_info = ', '.join(f"{k}={v}" for k, v in request.mapping.items() if k != 'type')
    mapping_type = request.mapping.get('type', 'unknown')

    title_context = ""
    if request.widget_title:
        title_context += f"\nWidget title: {request.widget_title}"
    if request.widget_description:
        title_context += f"\nWidget description: {request.widget_description}"

    prompt = f"""You are a SQL expert. Fix the SQL query that produced an error.

Original SQL:
```sql
{request.sql}
```

Error:
{request.error_message}

Widget type: {mapping_type}
Expected output columns: {mapping_info}
Database type: {connection.db_type}{title_context}
IMPORTANT: Only use table and column names that exist in the schema below. Do NOT invent table or column names.
"""

    if title_context:
        prompt += """
SEMANTIC CHECK: The fixed SQL must correctly query data that matches the widget title.
For example, if the title says "Average Price", the SQL must query a price-related column — not floor_area, size, or other unrelated columns.
"""

    if schema_summary:
        prompt += f"\nDatabase schema:\n{schema_summary}\n"

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

        # Strip markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r'^```[a-z]*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()

        import json
        result = json.loads(content)
        return WidgetSuggestFixResponse(
            suggested_sql=result["suggested_sql"],
            explanation=result["explanation"],
        )
    except Exception as e:
        logger.error(f"suggest_fix LLM call failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {e}")
