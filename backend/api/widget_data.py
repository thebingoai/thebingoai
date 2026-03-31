import re
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

# Regex to find WHERE/GROUP BY/ORDER BY/HAVING/LIMIT clause boundaries (case-insensitive)
_KEYWORD_PATTERN = re.compile(
    r'\b(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET)\b',
    re.IGNORECASE,
)
_WHERE_PATTERN = re.compile(r'\bWHERE\b', re.IGNORECASE)


def _depth_at(sql: str, pos: int) -> int:
    """Return parenthesis nesting depth at *pos* (counted from the start of *sql*)."""
    depth = 0
    for i in range(pos):
        if sql[i] == '(':
            depth += 1
        elif sql[i] == ')':
            depth -= 1
    return depth


def _find_top_level_matches(sql: str, pattern: re.Pattern) -> list[re.Match]:
    """Return all matches of *pattern* that sit at parenthesis depth 0."""
    matches: list[re.Match] = []
    depth = 0
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == '(':
            depth += 1
            i += 1
        elif ch == ')':
            depth -= 1
            i += 1
        elif depth == 0:
            m = pattern.match(sql, i)
            if m:
                matches.append(m)
                i = m.end()
            else:
                i += 1
        else:
            i += 1
    return matches


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


def inject_filters(
    sql: str,
    filters: List[FilterParam],
    data_context: dict | None = None,
    widget_sources: list[str] | None = None,
) -> Tuple[str, dict]:
    """
    Inject filter conditions into a SQL query by adding/extending the WHERE clause.

    Returns (modified_sql, params_dict) where params_dict contains the parameterized values.
    Column names are double-quoted to handle reserved words and mixed case.
    Values are parameterized to prevent SQL injection.

    If data_context and widget_sources are provided, only filters whose dimensions
    apply to the widget's sources are injected (dimension-aware mode).
    """
    if not filters:
        return sql, {}

    # Dimension-aware: filter out inapplicable filters
    if data_context and widget_sources:
        filters = [
            f for f in filters
            if _dimension_applies_to_sources(f.column, data_context, widget_sources)
        ]
        if not filters:
            return sql, {}

    # Strip trailing semicolons so appended conditions don't create multiple statements
    sql = sql.rstrip().rstrip(';').rstrip()

    params: dict = {}
    conditions: list[str] = []

    op_map = {
        'eq': '=',
        'neq': '!=',
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<=',
        'ilike': 'ILIKE',
    }

    for i, f in enumerate(filters):
        col = f'"{f.column}"'
        if f.op == 'in':
            values = f.value if isinstance(f.value, list) else [f.value]
            placeholders = []
            for j, v in enumerate(values):
                pk = f'_f{i}_{j}'
                placeholders.append(f'%({pk})s')
                params[pk] = v
            conditions.append(f'{col} IN ({", ".join(placeholders)})')
        else:
            param_key = f'_f{i}'
            op = op_map[f.op]
            conditions.append(f'{col} {op} %({param_key})s')
            params[param_key] = f.value

    condition_clause = ' AND '.join(conditions)

    # Find ALL top-level (depth-0) WHERE and keyword matches
    where_matches = _find_top_level_matches(sql, _WHERE_PATTERN)
    keyword_matches = _find_top_level_matches(sql, _KEYWORD_PATTERN)

    if where_matches:
        # Use the LAST top-level WHERE (the outermost query's WHERE)
        last_where = where_matches[-1]
        # Find the first top-level keyword AFTER this WHERE
        after_keywords = [m for m in keyword_matches if m.start() > last_where.end()]
        if after_keywords:
            insert_pos = after_keywords[0].start()
            modified = sql[:insert_pos].rstrip() + f' AND {condition_clause} ' + sql[insert_pos:]
        else:
            modified = sql.rstrip() + f' AND {condition_clause}'
    else:
        if keyword_matches:
            insert_pos = keyword_matches[0].start()
            modified = sql[:insert_pos].rstrip() + f' WHERE {condition_clause} ' + sql[insert_pos:]
        else:
            modified = sql.rstrip() + f' WHERE {condition_clause}'

    return modified, params

def inject_filters_sqlite(
    table_name: str,
    filters: List[FilterParam],
    data_context: dict | None = None,
    widget_sources: list[str] | None = None,
) -> Tuple[str, list]:
    """Build a SELECT query with WHERE filters for a SQLite cache table.

    Returns (sql, params) where params is a list of values for ? placeholders.
    Table and column names are quoted to prevent SQL injection.
    """
    base = f'SELECT * FROM "{table_name}"'

    if not filters:
        return base, []

    # Dimension-aware: filter out inapplicable filters
    if data_context and widget_sources:
        filters = [
            f for f in filters
            if _dimension_applies_to_sources(f.column, data_context, widget_sources)
        ]
        if not filters:
            return base, []

    conditions: list[str] = []
    params: list = []

    op_map = {
        'eq': '=',
        'neq': '!=',
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<=',
        'ilike': 'LIKE',
    }

    for f in filters:
        col = f'"{f.column}"'
        if f.op == 'in':
            values = f.value if isinstance(f.value, list) else [f.value]
            placeholders = ', '.join(['?'] * len(values))
            conditions.append(f'{col} IN ({placeholders})')
            params.extend(values)
        else:
            op = op_map[f.op]
            conditions.append(f'{col} {op} ?')
            params.append(f.value)

    where = ' AND '.join(conditions)
    return f'{base} WHERE {where}', params


def _read_widget_from_cache(
    dashboard_id: int,
    widget_id: str,
    filters: list[FilterParam] | None = None,
    data_context: dict | None = None,
    widget_sources: list[str] | None = None,
) -> "QueryResult":
    """Read widget data from SQLite cache, with optional filter injection.

    Returns a QueryResult compatible with transform_widget_data().
    Raises FileNotFoundError if cache is unavailable, ValueError if widget table missing.
    """
    import sqlite3
    import time
    from backend.connectors.base import QueryResult
    from backend.services.dashboard_cache import get_cache_path, _sanitize_widget_id

    cache_path = get_cache_path(dashboard_id)
    table_name = _sanitize_widget_id(widget_id)

    start_time = time.time()

    sql, params = inject_filters_sqlite(
        table_name, filters or [],
        data_context=data_context,
        widget_sources=widget_sources,
    )

    uri = f"file:{cache_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        # Verify table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cursor.fetchone():
            raise ValueError(f"Widget table '{table_name}' not found in cache")

        cursor = conn.execute(sql, params)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=execution_time_ms,
        )
    finally:
        conn.close()


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

    If the dashboard has a ready SQLite cache and widget_id is provided,
    reads from cache instead of hitting the source DB. Falls back to source
    DB if cache is unavailable or stale.
    """
    # Load dashboard once (used for cache check + dimension-aware filters)
    dashboard = None
    if request.dashboard_id:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == request.dashboard_id,
            Dashboard.user_id == current_user.id,
        ).first()

    # Cache metadata for responses
    _cache_built_at = str(dashboard.cache_built_at) if dashboard and dashboard.cache_built_at else None
    _cache_status = dashboard.cache_status if dashboard else None

    # Try cache path when dashboard has a ready cache and widget_id is provided
    if dashboard and dashboard.cache_status == 'ready' and request.widget_id:
        try:
            result = _read_widget_from_cache(
                request.dashboard_id,
                request.widget_id,
                filters=request.filters,
                data_context=dashboard.data_context,
                widget_sources=request.widget_sources,
            )
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
                cache_built_at=_cache_built_at,
                cache_status=_cache_status,
            )
        except Exception as e:
            logger.warning(f"Cache read failed for widget {request.widget_id}, falling back to source DB: {e}")

    # Fallback: source DB query (original behavior)
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
            cache_built_at=_cache_built_at,
            cache_status=_cache_status,
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

    If the dashboard has a ready SQLite cache, reads all widget tables from
    a single local file instead of hitting N source-DB connections.

    Widgets without a dataSource are skipped. Each widget result is keyed
    by widget id. Failures per-widget are captured as {error} rather than
    failing the entire request.
    """
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()

    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    widgets = dashboard.widgets or []
    results: dict = {}

    _cache_built_at = str(dashboard.cache_built_at) if dashboard.cache_built_at else None
    _cache_status = dashboard.cache_status

    # Try cache path: open SQLite once, read all widget tables
    if dashboard.cache_status == 'ready':
        try:
            from backend.connectors.base import QueryResult
            from backend.services.dashboard_cache import get_cache_path, read_widget_data

            cache_path = get_cache_path(dashboard_id)
            refreshed_at = datetime.now(timezone.utc).isoformat()

            for widget in widgets:
                widget_id = widget.get("id")
                data_source = widget.get("dataSource")
                if not data_source:
                    continue
                mapping = data_source.get("mapping")
                if not mapping:
                    results[widget_id] = {"error": "Incomplete dataSource (missing mapping)"}
                    continue
                try:
                    data = read_widget_data(cache_path, widget_id)
                    query_result = QueryResult(
                        columns=data["columns"],
                        rows=data["rows"],
                        row_count=data["row_count"],
                        execution_time_ms=0,
                    )
                    config = transform_widget_data(query_result, mapping)
                    results[widget_id] = {"config": config, "refreshed_at": refreshed_at}
                except Exception as e:
                    logger.error(f"Cache read failed for widget {widget_id}: {e}")
                    results[widget_id] = {"error": str(e)}

            return BulkRefreshResponse(
                widgets=results,
                cache_built_at=_cache_built_at,
                cache_status=_cache_status,
            )
        except FileNotFoundError:
            logger.warning(f"Cache file not found for dashboard {dashboard_id}, falling back to source DB")

    # Fallback: source DB queries (original behavior)
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
            result = connector.execute_query(sql)
            config = transform_widget_data(result, mapping)
            refreshed_at = datetime.now(timezone.utc).isoformat()
            results[widget_id] = {"config": config, "refreshed_at": refreshed_at}
        except Exception as e:
            logger.error(f"Bulk refresh failed for widget {widget_id}: {e}")
            results[widget_id] = {"error": str(e)}
        finally:
            connector.close()

    return BulkRefreshResponse(
        widgets=results,
        cache_built_at=_cache_built_at,
        cache_status=_cache_status,
    )


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
