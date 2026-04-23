from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.sql_query import SqlQueryRequest, SqlQueryResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["sql-query"])


@router.post("/{connection_id}/query", response_model=SqlQueryResponse)
async def execute_sql_query(
    connection_id: str,
    request: SqlQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute a read-only SQL query against a database connection.

    Only SELECT queries are permitted. Multi-statement queries and
    dangerous keywords (INSERT, UPDATE, DELETE, DROP, etc.) are blocked.
    """
    # Verify connection ownership — accept either numeric id or UUID
    key_str = str(connection_id)
    q = db.query(DatabaseConnection)
    if key_str.isdigit():
        connection = q.filter(
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.id == int(key_str),
        ).first()
    else:
        connection = q.filter(
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.uuid == key_str,
        ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    from backend.connectors.factory import get_connector_for_connection

    connector = get_connector_for_connection(connection)

    try:
        result = connector.execute_query(request.sql)

        # Apply row limit and detect truncation
        rows = [list(row) for row in result.rows]
        truncated = len(rows) > request.limit
        if truncated:
            rows = rows[:request.limit]

        return SqlQueryResponse(
            columns=result.columns,
            rows=rows,
            row_count=result.row_count,
            execution_time_ms=result.execution_time_ms,
            truncated=truncated
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SQL query execution failed for connection {connection_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")
    finally:
        connector.close()
