"""Tool composition for the Dashboard Agent."""
from typing import List, Callable
from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.dashboard_tools import build_dashboard_tools
from backend.config import settings


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
        return dashboard_creation_tools + comm_tools

    # Default: inline data exploration tools
    db_tools = build_data_agent_tools(context)
    return db_tools + dashboard_creation_tools
