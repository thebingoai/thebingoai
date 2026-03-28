from langchain_core.tools import tool
from typing import List, Dict, Any, Callable
from decimal import Decimal
from datetime import date, datetime
from backend.services.schema_discovery import load_schema_file
from backend.connectors.factory import get_connector_for_connection
from backend.database.session import SessionLocal
from backend.models.database_connection import DatabaseConnection
from backend.connectors.factory import get_connector_registration
from backend.agents.context import AgentContext
from backend.services.query_result_store import store_query_result, publish_query_result
import uuid
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
    def list_tables(connection_id: int) -> str:
        """
        List all tables in a database connection.

        Args:
            connection_id: Database connection ID

        Returns:
            Comma-separated table names, or a message if none found
        """
        if not context.can_access_connection(connection_id):
            return f"Error: Connection {connection_id} not authorized or not available"

        try:
            schema_json = load_schema_file(connection_id)
            tables = schema_json.get("table_names", [])
            if not tables:
                return "No tables found in this connection. The database is empty or the schema has not been discovered yet."
            return ", ".join(tables)
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return "No schema file found for this connection. Try refreshing the schema first."

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
            return {"error": f"Connection {connection_id} not authorized or not available"}

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

            return {"error": f"Table '{table_name}' not found in this connection."}
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return {"error": "No schema file found for this connection. Try refreshing the schema first."}

    @tool
    def search_tables(connection_id: int, keyword: str) -> str:
        """
        Search for tables/columns matching a keyword.

        Args:
            connection_id: Database connection ID
            keyword: Search keyword (case-insensitive)

        Returns:
            Comma-separated matching table names, or a message if none found
        """
        if not context.can_access_connection(connection_id):
            return f"Error: Connection {connection_id} not authorized or not available"

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

            unique = list(set(matches))
            if not unique:
                return f"No tables or columns matching '{keyword}' found in this connection."
            return ", ".join(unique)
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return "No schema file found for this connection. Try refreshing the schema first."

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

            with get_connector_for_connection(connection) as connector:
                result = connector.execute_query(sql)

                # Build full result payload for frontend delivery
                full_result = {
                    "columns": result.columns,
                    "rows": [list(row) for row in result.rows],
                    "row_count": result.row_count,
                    "execution_time_ms": result.execution_time_ms,
                    "truncated": result.truncated,
                    "sql": sql,
                    "connection_id": connection_id,
                }

                # Store and publish full data to frontend via side-channel
                result_ref = str(uuid.uuid4())
                store_query_result(result_ref, context.user_id, full_result)
                publish_query_result(context.user_id, result_ref, full_result)

                # Return only metadata to the LLM — no actual data values
                return {
                    "columns": result.columns,
                    "row_count": result.row_count,
                    "execution_time_ms": result.execution_time_ms,
                    "result_ref": result_ref,
                    "truncated": result.truncated,
                }

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()

    @tool
    def profile_table(connection_id: int, table_name: str) -> Dict[str, Any]:
        """
        Profile a table's data distribution. Returns summary statistics for each column
        to inform dashboard design decisions. Call this before designing KPIs, charts,
        or filters — it reveals which columns have useful cardinality, numeric ranges,
        and date spans so you can make data-informed visualization choices.

        Args:
            connection_id: Database connection ID
            table_name: Name of the table to profile

        Returns:
            Dict with row_count and per-column statistics (min/max/avg for numeric,
            min/max for date, distinct_count + top_values for categorical)
        """
        if not context.can_access_connection(connection_id):
            return {"error": f"Connection {connection_id} not authorized or not available"}

        def _safe(val: Any) -> Any:
            if isinstance(val, Decimal):
                return float(val)
            if isinstance(val, (datetime, date)):
                return val.isoformat()
            return val

        try:
            schema_json = load_schema_file(connection_id)
        except FileNotFoundError:
            return {"error": f"Schema not cached for connection {connection_id}. Run schema discovery first."}

        # Find the table across all schemas
        found_schema = None
        table_data = None
        for schema_name, schema_data in schema_json.get("schemas", {}).items():
            if table_name in schema_data.get("tables", {}):
                found_schema = schema_name
                table_data = schema_data["tables"][table_name]
                break

        if table_data is None:
            return {"error": f"Table '{table_name}' not found in schema cache."}

        row_count = table_data.get("row_count", 0)
        all_columns = table_data.get("columns", [])[:30]  # cap at 30 columns

        NUMERIC_TYPES = {
            "integer", "bigint", "smallint", "numeric", "decimal", "real",
            "double precision", "float", "int", "tinyint", "mediumint",
            "float4", "float8", "int2", "int4", "int8", "serial", "bigserial",
        }
        DATE_TYPES = {
            "date", "timestamp", "timestamp without time zone",
            "timestamp with time zone", "datetime", "timestamptz",
        }

        numeric_cols, date_cols, text_cols = [], [], []
        for col in all_columns:
            col_type = col.get("type", "").split("(")[0].strip().lower()
            if col_type in NUMERIC_TYPES:
                numeric_cols.append(col["name"])
            elif col_type in DATE_TYPES:
                date_cols.append(col["name"])
            else:
                text_cols.append(col["name"])

        db = SessionLocal()
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == context.user_id,
            ).first()

            if not connection:
                return {"error": "Connection not found"}

            # Determine quoting and table name based on connection type
            reg = get_connector_registration(connection.db_type)
            is_dataset = reg is not None and reg.sql_dialect_hint is not None and "SQLite" in reg.sql_dialect_hint
            db_type_str = "mysql" if connection.db_type == "mysql" else "postgres"

            def q(name: str) -> str:
                return f"`{name}`" if db_type_str == "mysql" else f'"{name}"'

            if is_dataset:
                qualified_table = f'"{table_name}"'  # SQLite: use table name from schema
            else:
                qualified_table = f"{q(found_schema)}.{q(table_name)}"
            result_columns: Dict[str, Any] = {}

            with get_connector_for_connection(connection) as connector:

                # Query A: Numeric stats (min/max/avg/null_count per column)
                if numeric_cols:
                    try:
                        parts = []
                        for col in numeric_cols:
                            qc = q(col)
                            parts += [
                                f"MIN({qc})",
                                f"MAX({qc})",
                                f"AVG({qc})",
                                f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END)",
                            ]
                        res = connector.execute_query(
                            f"SELECT {', '.join(parts)} FROM {qualified_table}"
                        )
                        if res.rows:
                            row = res.rows[0]
                            for i, col in enumerate(numeric_cols):
                                b = i * 4
                                result_columns[col] = {
                                    "type": "numeric",
                                    "min": _safe(row[b]),
                                    "max": _safe(row[b + 1]),
                                    "avg": _safe(row[b + 2]),
                                    "null_count": _safe(row[b + 3]),
                                }
                    except Exception as e:
                        logger.warning(f"profile_table numeric stats failed for {table_name}: {e}")
                        for col in numeric_cols:
                            result_columns[col] = {"type": "numeric", "error": str(e)}

                # Query B: Date stats (min/max/null_count per column)
                if date_cols:
                    try:
                        parts = []
                        for col in date_cols:
                            qc = q(col)
                            parts += [
                                f"MIN({qc})",
                                f"MAX({qc})",
                                f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END)",
                            ]
                        res = connector.execute_query(
                            f"SELECT {', '.join(parts)} FROM {qualified_table}"
                        )
                        if res.rows:
                            row = res.rows[0]
                            for i, col in enumerate(date_cols):
                                b = i * 3
                                result_columns[col] = {
                                    "type": "date",
                                    "min": _safe(row[b]),
                                    "max": _safe(row[b + 1]),
                                    "null_count": _safe(row[b + 2]),
                                }
                    except Exception as e:
                        logger.warning(f"profile_table date stats failed for {table_name}: {e}")
                        for col in date_cols:
                            result_columns[col] = {"type": "date", "error": str(e)}

                # Query C: Categorical distinct counts (run before D — D is conditional on this)
                distinct_counts: Dict[str, int] = {}
                if text_cols:
                    try:
                        parts = []
                        for col in text_cols:
                            qc = q(col)
                            parts += [
                                f"COUNT(DISTINCT {qc})",
                                f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END)",
                            ]
                        res = connector.execute_query(
                            f"SELECT {', '.join(parts)} FROM {qualified_table}"
                        )
                        if res.rows:
                            row = res.rows[0]
                            for i, col in enumerate(text_cols):
                                b = i * 2
                                d_count = int(row[b]) if row[b] is not None else 0
                                distinct_counts[col] = d_count
                                result_columns[col] = {
                                    "type": "categorical",
                                    "distinct_count": d_count,
                                    "null_count": _safe(row[b + 1]),
                                }
                    except Exception as e:
                        logger.warning(f"profile_table categorical stats failed for {table_name}: {e}")
                        for col in text_cols:
                            result_columns[col] = {"type": "categorical", "error": str(e)}

                # Query D: Top 5 values per categorical column (only if distinct_count <= 100)
                for col in text_cols:
                    d_count = distinct_counts.get(col, 0)
                    if d_count == 0 or d_count > 100:
                        continue
                    try:
                        qc = q(col)
                        res = connector.execute_query(
                            f"SELECT {qc}, COUNT(*) FROM {qualified_table} "
                            f"WHERE {qc} IS NOT NULL "
                            f"GROUP BY {qc} ORDER BY 2 DESC LIMIT 5"
                        )
                        top_values = [_safe(row[0]) for row in res.rows]
                        if col in result_columns:
                            result_columns[col]["top_values"] = top_values
                    except Exception as e:
                        logger.warning(f"profile_table top values failed for {table_name}.{col}: {e}")

            return {
                "table_name": table_name,
                "row_count": row_count,
                "columns": result_columns,
            }

        except Exception as e:
            logger.exception(f"profile_table failed for {table_name}")
            return {"error": f"{type(e).__name__}: {e}" or "Unknown error"}
        finally:
            db.close()

    # Return list of tools with captured context
    return [list_tables, get_table_schema, search_tables, execute_query, profile_table]


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


def build_profile_table_tool(context: AgentContext) -> List:
    """Return [profile_table] tool bound to *context*."""
    tools = build_data_agent_tools(context)
    return [t for t in tools if t.name == "profile_table"]
