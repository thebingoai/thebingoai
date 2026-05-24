from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.models.dashboard import Dashboard
from backend.schemas.widget_data import FilterParam, WidgetRefreshRequest, WidgetRefreshResponse, BulkRefreshResponse, WidgetSuggestFixRequest, WidgetSuggestFixResponse
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
    # Dimension not found in context — apply anyway (backward compat)
    return True


_OP_MAP = {
    'eq': '=',
    'neq': '!=',
    'gt': '>',
    'gte': '>=',
    'lt': '<',
    'lte': '<=',
    'ilike': 'ILIKE',
}

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
) -> Tuple[str, dict]:
    """
    Inject filter conditions into widget SQL using sqlglot's AST.

    The injector picks the innermost SELECT scope whose real-table sources cover
    every filter column (push-down before aggregation). If no scope covers all
    columns, the outermost SELECT is used (post-aggregation filter on widget
    output). Calendar-bounds CTEs and similar FROM-less scopes are skipped
    automatically because their `scope.sources` are empty.

    Returns (modified_sql, params_dict). Values are parameterized via psycopg2
    `%(key)s` placeholders. Column names are emitted as quoted identifiers so
    reserved words and mixed-case names round-trip safely.

    If parsing fails (non-BQ dialect, malformed SQL), falls back to a
    dialect-neutral subquery wrap: `SELECT * FROM (<sql>) AS _wf WHERE ...`.
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
        modified = _inject_via_sqlglot(sql, filters, ast_conditions, data_context)
    except Exception as e:
        logger.warning(
            "inject_filters: sqlglot rewrite failed (%s); falling back to subquery wrap",
            e,
        )
        modified = _wrap_subquery_fallback(sql, params, filters)

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
    cond = op_to_exp[f.op](this=col, expression=exp.Placeholder(this=pk))
    return cond, {pk: f.value}


def _inject_via_sqlglot(
    sql: str,
    filters: List[FilterParam],
    conditions: list,
    data_context: dict | None,
) -> str:
    """Parse *sql* as BigQuery, pick the best SELECT scope, attach WHERE there.

    Raises on parse failure so the caller can route to the subquery-wrap fallback.
    """
    import sqlglot
    from sqlglot import exp
    from sqlglot.optimizer.scope import build_scope

    ast = sqlglot.parse_one(sql, dialect="bigquery")
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
        target_scope = root_scope

    target_select = target_scope.expression
    if not isinstance(target_select, exp.Select):
        raise ValueError(f"target scope is not a SELECT: {type(target_select).__name__}")

    for cond in conditions:
        target_select.where(cond, append=True, copy=False)

    rendered = ast.sql(dialect="bigquery")
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
) -> str:
    """Dialect-neutral fallback when sqlglot can't parse the SQL.

    Wraps the original query as a subquery and applies the WHERE on top. The
    filter column must survive into the subquery's output for this to work; for
    widgets that's normally true because filter columns are dimensions and
    dashboards project their dimensions.
    """
    conditions: list[str] = []
    for i, f in enumerate(filters):
        col = f'"{f.column}"'
        if f.op == 'in':
            values = f.value if isinstance(f.value, list) else [f.value]
            placeholders = [f'%(_f{i}_{j})s' for j in range(len(values))]
            conditions.append(f'{col} IN ({", ".join(placeholders)})')
        else:
            op = _OP_MAP[f.op]
            conditions.append(f'{col} {op} %(_f{i})s')
    condition_clause = ' AND '.join(conditions)
    return f"SELECT * FROM (\n{sql}\n) AS _wf WHERE {condition_clause}"

def _read_widget_from_cache(
    dashboard_id: int,
    widget_id: str,
    org_id: str | None = None,
    user_id: str | None = None,
) -> "QueryResult | None":
    """Read widget data from the DataPlane Parquet cache.

    Returns a QueryResult on hit, or None when the table doesn't exist yet
    (cold cache → caller should fall back to the source connector).
    """
    import time
    from backend.connectors.base import QueryResult
    from backend.services.dashboard_cache import read_widget_data_plane

    start = time.time()
    dp_data = read_widget_data_plane(dashboard_id, widget_id, org_id, user_id or "")
    if dp_data is None:
        return None
    return QueryResult(
        columns=dp_data["columns"],
        rows=dp_data["rows"],
        row_count=dp_data["row_count"],
        execution_time_ms=(time.time() - start) * 1000,
    )


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

    When the dashboard has a Parquet cache on the DataPlane and no filters
    are applied, reads from the cache instead of hitting the source DB.
    Falls back to the source DB on cache miss or when filters are requested.
    """
    dashboard = None
    if request.dashboard_id:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == request.dashboard_id,
            Dashboard.user_id == current_user.id,
        ).first()

    # DataPlane cache read — only when no filters (Parquet has no WHERE injection).
    if dashboard and request.widget_id and not request.filters:
        try:
            result = _read_widget_from_cache(
                request.dashboard_id,
                request.widget_id,
                org_id=getattr(current_user, "org_id", None),
                user_id=current_user.id,
            )
            if result is not None:
                config = transform_widget_data(result, request.mapping)
                return WidgetRefreshResponse(
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
                )
        except Exception as e:
            logger.warning(f"DataPlane cache read failed for widget {request.widget_id}, falling back to source DB: {e}")

    # Fallback: source DB query
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == request.connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    from backend.connectors.factory import get_connector_for_connection

    connector = get_connector_for_connection(connection)

    try:
        sql = request.sql
        params = None
        if request.filters:
            data_context = dashboard.data_context if dashboard else None
            sql, params = inject_filters(
                sql, request.filters,
                data_context=data_context,
                widget_sources=request.widget_sources,
            )

        # Route bigquery_ga4 widget SQL through the data plane (managed
        # materialised view) instead of the raw GA4 source connector.
        if connection.db_type == "bigquery_ga4":
            from backend.data_plane.scope import OwnerScope
            from backend.models.pipeline import Pipeline
            from backend.services.data_plane_service import get_default_plane
            _p = db.query(Pipeline).filter(
                Pipeline.source_connection_id == connection.id,
            ).first()
            if _p is not None:
                _scope = OwnerScope(kind=_p.owner_scope_kind, id=_p.owner_scope_id)
                _plane = get_default_plane(_scope, db)
                result = _plane.query(_scope, sql, params=params)
            else:
                result = connector.execute_query(sql, params=params)
        else:
            result = connector.execute_query(sql, params=params)

        config = transform_widget_data(result, request.mapping)

        return WidgetRefreshResponse(
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
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Widget refresh failed for connection {request.connection_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")
    finally:
        connector.close()


@router.post("/{dashboard_id}/refresh", response_model=BulkRefreshResponse)
async def refresh_dashboard_widgets(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Re-execute SQL queries for all SQL-backed widgets in a dashboard.

    Each widget is read from the DataPlane Parquet cache when available;
    on cold cache the widget falls back to its source connector. Widgets
    without a dataSource are skipped; per-widget failures are captured as
    {error} rather than failing the entire request.
    """
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    widgets = dashboard.widgets or []
    results: dict = {}
    org_id = getattr(current_user, "org_id", None)
    refreshed_at = datetime.now(timezone.utc).isoformat()

    for widget in widgets:
        widget_id = widget.get("id")
        data_source = widget.get("dataSource")
        if not data_source:
            continue

        connection_id = data_source.get("connectionId")
        sql = data_source.get("sql")
        mapping = data_source.get("mapping")

        if not connection_id or not sql or not mapping:
            results[widget_id] = {"error": "Incomplete dataSource (missing connectionId, sql, or mapping)"}
            continue

        chart_type = widget.get("widget", {}).get("config", {}).get("type")
        if chart_type and "chartType" not in mapping:
            mapping = {**mapping, "chartType": chart_type}

        # Try DataPlane cache first.
        try:
            cached = _read_widget_from_cache(
                dashboard_id, widget_id,
                org_id=org_id, user_id=current_user.id,
            )
            if cached is not None:
                results[widget_id] = {
                    "config": transform_widget_data(cached, mapping),
                    "refreshed_at": refreshed_at,
                }
                continue
        except Exception as e:
            logger.warning(f"DataPlane cache read failed for widget {widget_id}, falling back to source DB: {e}")

        # Fallback: source DB query.
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
            DatabaseConnection.user_id == current_user.id,
        ).first()

        if not connection:
            results[widget_id] = {"error": f"Connection {connection_id} not found"}
            continue

        from backend.connectors.factory import get_connector_for_connection

        connector = get_connector_for_connection(connection)

        try:
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
                    result = _plane.query(_s, sql)
                else:
                    result = connector.execute_query(sql)
            else:
                result = connector.execute_query(sql)
            results[widget_id] = {
                "config": transform_widget_data(result, mapping),
                "refreshed_at": refreshed_at,
            }
        except Exception as e:
            logger.error(f"Bulk refresh failed for widget {widget_id}: {e}")
            results[widget_id] = {"error": str(e)}
        finally:
            connector.close()

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
