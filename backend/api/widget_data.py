import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.models.dashboard import Dashboard
from backend.schemas.widget_data import FilterParam, WidgetRefreshRequest, WidgetRefreshResponse, BulkRefreshResponse
from backend.services.widget_transform import transform_widget_data
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Regex to find WHERE/GROUP BY/ORDER BY/HAVING/LIMIT clause boundaries (case-insensitive)
_KEYWORD_PATTERN = re.compile(
    r'\b(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET)\b',
    re.IGNORECASE,
)
_WHERE_PATTERN = re.compile(r'\bWHERE\b', re.IGNORECASE)


def inject_filters(sql: str, filters: List[FilterParam]) -> Tuple[str, dict]:
    """
    Inject filter conditions into a SQL query by adding/extending the WHERE clause.

    Returns (modified_sql, params_dict) where params_dict contains the parameterized values.
    Column names are double-quoted to handle reserved words and mixed case.
    Values are parameterized to prevent SQL injection.
    """
    if not filters:
        return sql, {}

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
        param_key = f'_f{i}'
        col = f'"{f.column}"'
        op = op_map[f.op]
        conditions.append(f'{col} {op} %({param_key})s')
        params[param_key] = f.value

    condition_clause = ' AND '.join(conditions)

    where_match = _WHERE_PATTERN.search(sql)
    if where_match:
        # Find where the next major keyword starts after WHERE to insert AND conditions
        keyword_match = _KEYWORD_PATTERN.search(sql, where_match.end())
        if keyword_match:
            insert_pos = keyword_match.start()
            modified = sql[:insert_pos].rstrip() + f' AND {condition_clause} ' + sql[insert_pos:]
        else:
            modified = sql.rstrip() + f' AND {condition_clause}'
    else:
        keyword_match = _KEYWORD_PATTERN.search(sql)
        if keyword_match:
            insert_pos = keyword_match.start()
            modified = sql[:insert_pos].rstrip() + f' WHERE {condition_clause} ' + sql[insert_pos:]
        else:
            modified = sql.rstrip() + f' WHERE {condition_clause}'

    return modified, params

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
    """
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == request.connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    from backend.connectors.factory import get_connector

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
        sql = request.sql
        params = None
        if request.filters:
            sql, params = inject_filters(sql, request.filters)

        result = connector.execute_query(sql, params=params)

        # Apply row limit
        truncated = result.row_count > request.limit
        if truncated:
            from backend.connectors.base import QueryResult
            result = QueryResult(
                columns=result.columns,
                rows=result.rows[:request.limit],
                row_count=result.row_count,
                execution_time_ms=result.execution_time_ms,
            )

        config = transform_widget_data(result, request.mapping)

        return WidgetRefreshResponse(
            config=config,
            execution_time_ms=result.execution_time_ms,
            row_count=result.row_count,
            truncated=truncated,
            refreshed_at=datetime.now(timezone.utc).isoformat(),
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

        from backend.connectors.factory import get_connector

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
            refreshed_at = datetime.now(timezone.utc).isoformat()
            results[widget_id] = {"config": config, "refreshed_at": refreshed_at}
        except Exception as e:
            logger.error(f"Bulk refresh failed for widget {widget_id}: {e}")
            results[widget_id] = {"error": str(e)}
        finally:
            connector.close()

    return BulkRefreshResponse(widgets=results)
