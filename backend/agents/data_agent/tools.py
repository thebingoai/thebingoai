from langchain_core.tools import tool
from typing import List, Dict, Any, Callable
from backend.services.schema_discovery import load_schema_file
from backend.connectors.factory import get_connector
from backend.database.session import SessionLocal
from backend.models.database_connection import DatabaseConnection
from backend.agents.context import AgentContext
import logging

logger = logging.getLogger(__name__)


def build_data_agent_tools(context: AgentContext) -> List[Callable]:
    """
    Build data agent tools with captured context via closure.

    Each tool instance captures its own AgentContext, enabling:
    - Thread-safe operation (no shared global state)
    - Multiple concurrent agent invocations
    - Clean separation of user contexts

    Args:
        context: AgentContext with user_id and available_connections

    Returns:
        List of LangChain tool functions with context captured
    """

    @tool
    def list_tables(connection_id: int) -> List[str]:
        """
        List all tables in a database connection.

        Args:
            connection_id: Database connection ID

        Returns:
            List of table names
        """
        if not context.can_access_connection(connection_id):
            return []

        try:
            schema_json = load_schema_file(connection_id)
            return schema_json.get("table_names", [])
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return []

    @tool
    def get_table_schema(connection_id: int, table_name: str) -> Dict[str, Any]:
        """
        Get detailed schema for a specific table.

        Args:
            connection_id: Database connection ID
            table_name: Name of the table

        Returns:
            Dict with columns (name, type, nullable, primary_key, foreign_key)
            and row_count
        """
        if not context.can_access_connection(connection_id):
            return {}

        try:
            schema_json = load_schema_file(connection_id)

            # Search for table in all schemas
            for schema_name, schema_data in schema_json.get("schemas", {}).items():
                if table_name in schema_data.get("tables", {}):
                    table_data = schema_data["tables"][table_name]
                    return {
                        "table_name": table_name,
                        "schema": schema_name,
                        "columns": table_data.get("columns", []),
                        "row_count": table_data.get("row_count", 0)
                    }

            return {}
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return {}

    @tool
    def search_tables(connection_id: int, keyword: str) -> List[str]:
        """
        Search for tables/columns matching a keyword.

        Args:
            connection_id: Database connection ID
            keyword: Search keyword (case-insensitive)

        Returns:
            List of matching table names
        """
        if not context.can_access_connection(connection_id):
            return []

        try:
            schema_json = load_schema_file(connection_id)
            keyword_lower = keyword.lower()
            matches = []

            # Search table names
            for table_name in schema_json.get("table_names", []):
                if keyword_lower in table_name.lower():
                    matches.append(table_name)
                    continue

                # Search column names
                for schema_name, schema_data in schema_json.get("schemas", {}).items():
                    if table_name in schema_data.get("tables", {}):
                        table_data = schema_data["tables"][table_name]
                        for column in table_data.get("columns", []):
                            if keyword_lower in column.get("name", "").lower():
                                matches.append(table_name)
                                break

            return list(set(matches))  # Remove duplicates
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return []

    @tool
    def execute_query(connection_id: int, sql: str) -> Dict[str, Any]:
        """
        Execute a read-only SQL query.

        Args:
            connection_id: Database connection ID
            sql: SQL query string (SELECT only)

        Returns:
            Dict with columns, rows, row_count, execution_time_ms, or error message
        """
        if not context.can_access_connection(connection_id):
            return {"error": "Connection not authorized"}

        # Get connection details
        db = SessionLocal()
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == context.user_id
            ).first()

            if not connection:
                return {"error": "Connection not found"}

            # Execute query
            with get_connector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                database=connection.database,
                username=connection.username,
                password=connection.password,
                ssl_enabled=connection.ssl_enabled,
                ssl_ca_cert=connection.ssl_ca_cert
            ) as connector:
                result = connector.execute_query(sql)

                return {
                    "columns": result.columns,
                    "rows": [list(row) for row in result.rows],
                    "row_count": result.row_count,
                    "execution_time_ms": result.execution_time_ms
                }

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()

    # Return list of tools with captured context
    return [list_tables, get_table_schema, search_tables, execute_query]


# ---------------------------------------------------------------------------
# Individual tool builder functions for use with the tool registry.
# Each builder returns a list containing the single tool it builds.
# ---------------------------------------------------------------------------

def build_list_tables_tool(context: AgentContext) -> List:
    """Return [list_tables] tool bound to *context*."""
    tools = build_data_agent_tools(context)
    return [t for t in tools if t.name == "list_tables"]


def build_get_table_schema_tool(context: AgentContext) -> List:
    """Return [get_table_schema] tool bound to *context*."""
    tools = build_data_agent_tools(context)
    return [t for t in tools if t.name == "get_table_schema"]


def build_search_tables_tool(context: AgentContext) -> List:
    """Return [search_tables] tool bound to *context*."""
    tools = build_data_agent_tools(context)
    return [t for t in tools if t.name == "search_tables"]


def build_execute_query_tool(context: AgentContext) -> List:
    """Return [execute_query] tool bound to *context*."""
    tools = build_data_agent_tools(context)
    return [t for t in tools if t.name == "execute_query"]
