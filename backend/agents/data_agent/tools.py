from langchain_core.tools import tool
from typing import List, Dict, Any, Callable, Optional
from decimal import Decimal
from datetime import date, datetime
from uuid import UUID
from backend.services.schema_discovery import load_schema_file
from backend.connectors.factory import get_connector_for_connection
from backend.database.session import SessionLocal, end_read_transaction
from backend.models.database_connection import DatabaseConnection
from backend.connectors.factory import get_connector_registration
from backend.agents.context import AgentContext
from backend.services.query_result_store import store_query_result, publish_query_result
import time
import uuid
import logging

logger = logging.getLogger(__name__)


def _coerce(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def _serve_query_via_dataplane(connection, sql: str, db) -> Optional[Any]:
    """Route an ad-hoc chat SQL query through the DataPlane when ready.

    Mirrors the dashboard widget plane-serve path (`api/widget_data.py`):
    rewrite source table refs → plane targets, then run via DuckDB over the
    plane (local Parquet in dev, GCS httpfs in prod). Returns a QueryResult on
    success, or None to fall back to live source (bootstrap policy: cold/missing
    Parquet, residency-locked plane, or any error → source-DB).
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
    from backend.utils.sql_refs import extract_table_refs, rewrite_table_refs

    table_map = plane_table_map(connection, db)
    if not table_map:
        return None  # no pipelines → bootstrap → live source

    # Agent generates SQL in the source dialect (its prompts use the source-DB
    # schema). Plane storage is Parquet served by DuckDB, so transpile first.
    # No-op when db_type == "duckdb" or absent. Failure → fall back to source.
    from backend.utils.sql_refs import (
        UntranspilableSQLError,
        transpile_to_engine,
    )

    db_type = (getattr(connection, "db_type", "") or "").lower()
    transpiled = sql
    if db_type and db_type != "duckdb":
        try:
            transpiled = transpile_to_engine(sql, source=db_type, target="duckdb")
        except UntranspilableSQLError:
            return None
        except Exception:
            return None

    try:
        from backend.utils.sql_refs import qualifier_allowlist
        base_sql, _ = rewrite_table_refs(transpiled, table_map, qualifier_allowlist(connection))
    except Exception:
        return None  # unparseable post-transpile SQL → live source

    plane, scope = get_plane_for_connection(connection, db)

    if isinstance(plane, LocalFilesystemDataPlane):
        try:
            tables = extract_table_refs(base_sql)
        except Exception:
            return None
        if not tables or not all(plane.table_exists(scope, t) for t in tables):
            return None  # cold/missing plane data → live source
        try:
            # Release before the Parquet scan (rationale: heartbeat_context.py).
            end_read_transaction(db)
            return plane.query(scope, base_sql)
        except Exception as e:
            logger.warning("Local plane chat serve failed (%s) — falling back", e)
            return None

    reader = None
    try:
        reader = get_gcs_duckdb_reader(scope, db)
        if reader is None:
            return None  # residency-locked / customer / no-HMAC → live source
        # Release before the Parquet read over GCS (same reasoning).
        end_read_transaction(db)
        return reader.query(scope, base_sql)
    except Exception as e:
        logger.warning("DuckDB-over-GCS chat serve failed (%s) — falling back", e)
        return None
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                pass


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
        from backend.services.seed import readable_connection_clause

        db = SessionLocal()
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                readable_connection_clause(context.user_id),
            ).first()

            if not connection:
                return {"error": "Connection not found"}

            # Plane redirect (flag-gated, per-Org). When the connection's
            # tables are materialized to the plane and `duckdb_widget_serving`
            # is on, run the query via DuckDB-over-DataPlane (Parquet) instead
            # of hammering the source DB. Cold/missing data → fall through.
            _t0 = time.perf_counter()
            result = _serve_query_via_dataplane(connection, sql, db)
            if result is None:
                with get_connector_for_connection(connection, db) as connector:
                    # Constructing the connector is the last Postgres read here;
                    # release before the query (rationale: heartbeat_context.py).
                    end_read_transaction(db)
                    result = connector.execute_query(sql)
            _total_ms = (time.perf_counter() - _t0) * 1000

            logger.info(
                "[LATENCY][execute_query] SQL exec: %sms total: %sms rows=%s connection=%s",
                round(result.execution_time_ms),
                round(_total_ms),
                result.row_count,
                connection_id,
            )

            # Short label from the primary table ref, used to name export files.
            from backend.utils.sql_refs import extract_table_refs
            tables = extract_table_refs(sql)
            label = tables[0] if tables else "query"

            # Privacy: under metadata_only_llm the LLM gets no row values, so the
            # chat bubble renders the side-channel result itself — it needs the flag.
            from backend.services.llm_privacy import (
                metadata_only_for_connection, strip_preview,
            )
            values_withheld = metadata_only_for_connection(connection)

            # Build full result payload for frontend delivery
            full_result = {
                "columns": result.columns,
                "rows": [[_coerce(v) for v in row] for row in result.rows],
                "row_count": result.row_count,
                "execution_time_ms": result.execution_time_ms,
                "truncated": result.truncated,
                "label": label,
                "sql": sql,
                "connection_id": connection_id,
                "values_withheld": values_withheld,
            }

            # Store and publish full data to frontend via side-channel
            result_ref = str(uuid.uuid4())
            store_query_result(result_ref, context.user_id, full_result)
            publish_query_result(context.user_id, result_ref, full_result)

            # Return metadata + first rows so the LLM can format tables
            preview_rows = [[_coerce(v) for v in row] for row in result.rows[:20]]
            preview = {
                "columns": result.columns,
                "rows": preview_rows,
                "row_count": result.row_count,
                "execution_time_ms": result.execution_time_ms,
                "result_ref": result_ref,
                "truncated": result.truncated,
            }
            # Withhold the preview rows from the LLM (the full result still
            # reaches the user via the side-channel above).
            if values_withheld:
                return strip_preview(preview)
            return preview

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()

    @tool
    def profile_table(connection_id: int, table_name: str) -> Dict[str, Any]:
        """
        Profile a table's structure. Returns per-column shape to inform dashboard design
        decisions. Call this before designing KPIs, charts, or filters — it reveals which
        columns have useful cardinality and how complete they are, so you can make
        structure-informed visualization choices.

        Args:
            connection_id: Database connection ID
            table_name: Name of the table to profile

        Returns:
            Dict with row_count and per-column type, null_count and distinct_count.
            Statistics computed from real records (avg, min/max, top_values) are
            included only when the org's privacy policy permits — do not rely on them,
            and never invent one when absent.
        """
        if not context.can_access_connection(connection_id):
            return {"error": f"Connection {connection_id} not authorized or not available"}

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

        from backend.services.seed import readable_connection_clause

        db = SessionLocal()
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                readable_connection_clause(context.user_id),
            ).first()

            if not connection:
                return {"error": "Connection not found"}

            reg = get_connector_registration(connection.db_type)
            is_dataset = reg is not None and reg.type_id == "dataset"
            db_type_str = "mysql" if connection.db_type == "mysql" else "postgres"

            from backend.services.table_profiler import profile_table as _profile

            with get_connector_for_connection(connection, db) as connector:
                # Profiling issues many source queries, none against Postgres.
                end_read_transaction(db)
                profile = _profile(
                    connector=connector,
                    table_name=table_name,
                    schema_name=found_schema,
                    columns=table_data.get("columns", []),
                    row_count=table_data.get("row_count", 0),
                    db_type=db_type_str,
                    is_dataset=is_dataset,
                )
            # Privacy: under metadata_only_llm, drop everything computed from real
            # records (min/max/top_values/avg) before the profile reaches the LLM;
            # keep the structural counts.
            from backend.services.llm_privacy import (
                metadata_only_for_connection, strip_profile_values,
            )
            if metadata_only_for_connection(connection):
                profile = strip_profile_values(profile)
            return profile
        except Exception as e:
            logger.exception(f"profile_table failed for {table_name}")
            return {"error": f"{type(e).__name__}: {e}" or "Unknown error"}
        finally:
            db.close()

    # Return list of tools with captured context
    core = [list_tables, get_table_schema, search_tables, execute_query, profile_table]

    # Append plugin-provided data-agent tools (e.g. query_ga4_pipeline). These
    # are explicit opt-ins via `BingoPlugin.data_agent_tool_builders()` -- they
    # only land here, not in the orchestrator's general tool pool, so the data
    # agent's prompt stays focused on SQL/analytics.
    try:
        from backend.agents.tool_registry import get_data_agent_plugin_tool_builders
        for name, builder in get_data_agent_plugin_tool_builders().items():
            try:
                core.extend(builder(context))
            except Exception:
                logger.exception("Failed to build data-agent plugin tool '%s'", name)
    except Exception:
        # Plugin registry not yet importable (early bootstrap); no plugin tools.
        pass
    return core


# ---------------------------------------------------------------------------
# Individual tool builder functions for use with the tool registry.
# Each builder returns a list containing the single tool it builds.
# ---------------------------------------------------------------------------

def _build_single_data_tool(name: str) -> Callable[[AgentContext], List]:
    """Return a builder that yields the single data-agent tool with this name."""

    def builder(context: AgentContext) -> List:
        return [t for t in build_data_agent_tools(context) if t.name == name]

    builder.__name__ = f"build_{name}_tool"
    builder.__doc__ = f"Return [{name}] tool bound to *context*."
    return builder


build_list_tables_tool = _build_single_data_tool("list_tables")
build_get_table_schema_tool = _build_single_data_tool("get_table_schema")
build_search_tables_tool = _build_single_data_tool("search_tables")
build_execute_query_tool = _build_single_data_tool("execute_query")
build_profile_table_tool = _build_single_data_tool("profile_table")
