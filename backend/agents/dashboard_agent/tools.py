"""Tool composition for the Dashboard Agent."""
from typing import List, Callable
from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.dashboard_tools import build_dashboard_tools
from backend.config import settings


@tool
def get_widget_spec(widget_type: str) -> str:
    """Get the complete configuration spec for a widget type.

    Call this BEFORE configuring a widget to get the authoritative field definitions,
    dataSource mapping structure, SQL patterns, and best practices.

    Args:
        widget_type: One of "kpi", "chart", "table", "filter", "text"

    Returns:
        Complete configuration spec for the widget type
    """
    from backend.agents.dashboard_agent.widget_specs import (
        get_widget_spec as _get_spec,
        get_available_types,
    )

    spec = _get_spec(widget_type)
    if spec is None:
        available = ", ".join(get_available_types())
        return f"Unknown widget type '{widget_type}'. Valid types: {available}"
    return spec


def _build_dashboard_context_tool(context: AgentContext, db_session_factory: Callable):
    """Build the build_dashboard_context tool bound to context and db_session_factory."""

    @tool
    def build_dashboard_context(connection_id: int, table_names: list, dimensions: list) -> str:
        """Assemble a dashboard data context from the pre-built connection context.

        Call this BEFORE writing any widget SQL. The returned context contains a
        baseJoin template — every data widget's SQL must include these JOINs so that
        dashboard filters can reach all dimensions.

        Args:
            connection_id: The connection to use (must have profiling_status "ready")
            table_names: Tables to include in the dashboard (from the connection context)
            dimensions: Column names to use as filterable dashboard dimensions

        Returns:
            JSON with sources, baseJoin, and dimension definitions
        """
        import json
        from backend.models.database_connection import DatabaseConnection
        from backend.services.connection_context import load_context_file

        if not context.can_access_connection(connection_id):
            return json.dumps({"success": False, "message": f"Connection {connection_id} not authorized"})

        db = db_session_factory()
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
            ).first()
            if not connection:
                return json.dumps({"success": False, "message": f"Connection {connection_id} not found"})

            if connection.profiling_status != "ready":
                return json.dumps({
                    "success": False,
                    "message": (
                        f"Connection '{connection.name}' is still being profiled "
                        f"({connection.profiling_progress or connection.profiling_status}). "
                        "Dashboard creation will be available once profiling completes."
                    ),
                })
        finally:
            db.close()

        try:
            conn_context = load_context_file(connection_id)
        except FileNotFoundError:
            return json.dumps({"success": False, "message": "Connection context not found. Try re-profiling."})

        ctx_tables = conn_context.get("tables", {})

        # Validate requested tables exist
        missing_tables = [t for t in table_names if t not in ctx_tables]
        if missing_tables:
            available = ", ".join(sorted(ctx_tables.keys()))
            return json.dumps({
                "success": False,
                "message": f"Table(s) not found: {', '.join(missing_tables)}. Available: {available}",
            })

        # Validate requested dimensions exist in the selected tables
        dim_defs = {}
        for dim_name in dimensions:
            found_in = []
            for tname in table_names:
                t_cols = ctx_tables[tname].get("columns", {})
                if dim_name in t_cols and t_cols[dim_name].get("role") in ("dimension",):
                    found_in.append(tname)
            if not found_in:
                # Check if it exists but isn't a dimension
                for tname in table_names:
                    t_cols = ctx_tables[tname].get("columns", {})
                    if dim_name in t_cols:
                        found_in.append(tname)
                if found_in:
                    dim_defs[dim_name] = found_in  # Allow non-dimension columns to be used as filters
                else:
                    all_dims = set()
                    for tname in table_names:
                        for cname, cdata in ctx_tables[tname].get("columns", {}).items():
                            if cdata.get("role") == "dimension":
                                all_dims.add(cname)
                    return json.dumps({
                        "success": False,
                        "message": (
                            f"Dimension '{dim_name}' not found in selected tables. "
                            f"Available dimensions: {', '.join(sorted(all_dims))}"
                        ),
                    })
            else:
                dim_defs[dim_name] = found_in

        # Build table aliases (first letter, ensure uniqueness)
        aliases: dict[str, str] = {}
        used: set[str] = set()
        for tname in table_names:
            alias = tname[0].lower()
            if alias in used:
                # Try first two letters, then first + number
                for i in range(2, len(tname) + 1):
                    alias = tname[:i].lower()
                    if alias not in used:
                        break
                else:
                    alias = tname.lower()
            aliases[tname] = alias
            used.add(alias)

        # Build baseJoin from relationships
        relationships = conn_context.get("relationships", [])
        primary_table = table_names[0]  # First table is the base
        join_clauses = []

        for tname in table_names[1:]:
            # Find a relationship between primary (or already joined tables) and this table
            joined_tables = {primary_table} | {t for t, _ in [(tn, None) for tn in table_names[:table_names.index(tname)]]}
            join_found = False

            for rel in relationships:
                from_table, from_col = rel["from"].split(".", 1)
                to_table, to_col = rel["to"].split(".", 1)

                if from_table == tname and to_table in joined_tables:
                    a_from = aliases[tname]
                    a_to = aliases[to_table]
                    join_clauses.append(
                        f"LEFT JOIN {tname} {a_from} ON {a_from}.{from_col} = {a_to}.{to_col}"
                    )
                    join_found = True
                    break
                elif to_table == tname and from_table in joined_tables:
                    a_from = aliases[from_table]
                    a_to = aliases[tname]
                    join_clauses.append(
                        f"LEFT JOIN {tname} {a_to} ON {a_from}.{from_col} = {a_to}.{to_col}"
                    )
                    join_found = True
                    break

            if not join_found:
                join_clauses.append(f"-- WARNING: No relationship found to join '{tname}'. Add a manual JOIN.")

        # Build sources
        sources = {}
        for tname in table_names:
            t_data = ctx_tables[tname]
            sources[tname] = {
                "connectionId": connection_id,
                "table": f"{t_data.get('schema', 'public')}.{tname}",
                "columns": list(t_data.get("columns", {}).keys()),
            }

        # Build dimension definitions
        dim_output = {}
        for dim_name, found_in_tables in dim_defs.items():
            primary_source = found_in_tables[0]
            alias = aliases[primary_source]
            col_data = ctx_tables[primary_source]["columns"].get(dim_name, {})
            dim_output[dim_name] = {
                "column": dim_name,
                "alias": f"{alias}.{dim_name}",
                "sources": found_in_tables,
                "type": col_data.get("type", "text"),
            }
            if col_data.get("cardinality") is not None:
                dim_output[dim_name]["cardinality"] = col_data["cardinality"]

        dashboard_context = {
            "sources": sources,
            "baseJoin": {
                "connectionId": connection_id,
                "from": f"{primary_table} {aliases[primary_table]}",
                "joins": join_clauses,
            },
            "dimensions": dim_output,
        }

        return json.dumps({"success": True, "data_context": dashboard_context})

    return build_dashboard_context


def _build_merge_datasets_tool(context: AgentContext, db_session_factory: Callable):
    """Build the merge_datasets tool for combining multiple CSV/Excel files."""

    @tool
    def merge_datasets(connection_ids: list, merged_name: str) -> str:
        """Merge multiple CSV/Excel dataset connections into a single multi-table database.

        Use this when a dashboard needs data from multiple uploaded files. Each file
        becomes a separate table in a single SQLite database, enabling JOINs and
        cross-file filtering.

        After merging, wait for profiling to complete before calling build_dashboard_context.

        Args:
            connection_ids: List of dataset connection IDs to merge
            merged_name: Name for the new merged connection (e.g. "Sales & Products")

        Returns:
            JSON with the new connection_id, table names, and row counts
        """
        import json

        for cid in connection_ids:
            if not context.can_access_connection(cid):
                return json.dumps({"success": False, "message": f"Connection {cid} not authorized"})

        db = db_session_factory()
        try:
            from bingo_csv_connector.service import merge_dataset_connections
            result = merge_dataset_connections(
                connection_ids=connection_ids,
                merged_name=merged_name,
                user_id=context.user_id,
                db_session=db,
            )
            return json.dumps({
                "success": True,
                **result,
                "message": (
                    f"Merged {len(connection_ids)} datasets into connection {result['connection_id']}. "
                    f"Tables: {', '.join(result['tables'])}. "
                    "Profiling is running in the background — wait for it to complete "
                    "before calling build_dashboard_context."
                ),
            })
        except ValueError as e:
            return json.dumps({"success": False, "message": str(e)})
        except ImportError:
            return json.dumps({
                "success": False,
                "message": "CSV connector plugin is not installed. Cannot merge datasets.",
            })
        except Exception as e:
            return json.dumps({"success": False, "message": f"Merge failed: {e}"})
        finally:
            db.close()

    return merge_datasets


def build_dashboard_agent_tools(
    context: AgentContext,
    db_session_factory: Callable,
) -> List:
    """
    Build the full tool set for the dashboard agent.

    When mesh is disabled (default):
        - DB exploration tools from data_agent (list_tables, get_table_schema, search_tables, execute_query)
        - Dashboard creation tool from dashboard_tools (create_dashboard)

    When mesh is enabled:
        - Dashboard creation tool only (data exploration delegated to data_agent peer)
        - Communication tools (sessions_send, sessions_list, etc.)

    Args:
        context: AgentContext with user_id and available_connections
        db_session_factory: Callable that returns a SQLAlchemy session

    Returns:
        List of LangChain tools
    """
    dashboard_creation_tools = build_dashboard_tools(context, db_session_factory)

    if settings.agent_mesh_enabled and context.session_id:
        # Mesh mode: delegate data exploration to data_agent via communication tools
        from backend.agents.communication_tools import build_communication_tools
        from backend.services.agent_registry import AgentRegistry
        from backend.services.agent_message_bus import AgentMessageBus

        registry = AgentRegistry()
        db = db_session_factory()
        message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)

        comm_tools = build_communication_tools(
            user_id=context.user_id,
            session_id=context.session_id,
            message_bus=message_bus,
            registry=registry,
        )
        context_tool = _build_dashboard_context_tool(context, db_session_factory)
        return dashboard_creation_tools + comm_tools + [get_widget_spec, context_tool]

    # Default: inline data exploration tools
    db_tools = build_data_agent_tools(context)
    context_tool = _build_dashboard_context_tool(context, db_session_factory)
    merge_tool = _build_merge_datasets_tool(context, db_session_factory)
    return db_tools + dashboard_creation_tools + [get_widget_spec, context_tool, merge_tool]
