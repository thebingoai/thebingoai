"""Tool composition for the Dashboard Agent."""
from typing import List, Callable
from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.dashboard_tools import build_dashboard_tools


def build_dashboard_agent_tools(
    context: AgentContext,
    db_session_factory: Callable,
) -> List:
    """
    Build the full tool set for the dashboard agent.

    Combines:
    - DB exploration tools from data_agent (list_tables, get_table_schema, search_tables, execute_query)
    - Dashboard creation tool from dashboard_tools (create_dashboard)

    Args:
        context: AgentContext with user_id and available_connections
        db_session_factory: Callable that returns a SQLAlchemy session

    Returns:
        List of LangChain tools
    """
    db_tools = build_data_agent_tools(context)
    dashboard_creation_tools = build_dashboard_tools(context, db_session_factory)
    return db_tools + dashboard_creation_tools
