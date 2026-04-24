"""
Tool Registry — maps tool_key strings (stored in DB) to Python tool-builder functions.

Each builder receives an AgentContext and returns a list of LangChain tools.
New tools are registered here by adding an entry to TOOL_BUILDERS.
"""
import inspect
from typing import Dict, Callable, List, Optional
from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import (
    build_list_tables_tool,
    build_get_table_schema_tool,
    build_search_tables_tool,
    build_execute_query_tool,
)
from backend.agents.dashboard_tools import build_create_dashboard_tool
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RAG search builder (lazy import to avoid circular deps at module load)
# ---------------------------------------------------------------------------

def _build_rag_search_tool(context: AgentContext) -> List:
    """Return [rag_search] tool that delegates to the RAG agent."""
    from langchain_core.tools import tool
    from backend.agents.rag_agent import invoke_rag_agent
    import json

    @tool
    async def rag_search(question: str, namespace: str = "default") -> str:
        """
        Search uploaded documents using semantic search.

        Args:
            question: Question about documents
            namespace: Vector namespace (default: "default")

        Returns:
            JSON string with answer and source context
        """
        result = await invoke_rag_agent(question, context, namespace)
        return json.dumps(result)

    return [rag_search]


def _build_recall_memory_tool(context: AgentContext) -> List:
    """Return [recall_memory] tool backed by MemoryRetriever."""
    from langchain_core.tools import tool
    from backend.memory.retriever import MemoryRetriever
    import json

    @tool
    async def recall_memory(query: str) -> str:
        """
        Recall past conversation context and patterns.

        Args:
            query: What to recall — topics, tables, patterns, past questions

        Returns:
            JSON with relevant past interactions or empty if none found
        """
        retriever = MemoryRetriever()
        context_str = await retriever.get_relevant_context(
            user_id=context.user_id, query=query, top_k=5
        )
        if not context_str:
            return json.dumps({"success": True, "memories": [], "message": "No relevant memories found"})
        return json.dumps({"success": True, "memories": context_str})

    return [recall_memory]


def _build_summarize_tool(context: AgentContext) -> List:
    """Return [summarize_text] tool from the skill registry."""
    from backend.agents.skills import get_skill_registry
    registry = get_skill_registry()
    all_tools = registry.to_tools()
    return [t for t in all_tools if getattr(t, "name", None) == "summarize_text"]


# ---------------------------------------------------------------------------
# Registry mapping
# ---------------------------------------------------------------------------

def _build_dashboard_agent_tool(context: AgentContext) -> List:
    """Return [dashboard_agent] tool that delegates to the dashboard sub-agent."""
    from langchain_core.tools import tool
    from backend.agents.dashboard_agent import invoke_dashboard_agent
    from backend.database.session import SessionLocal
    import json

    @tool
    async def dashboard_agent(request: str) -> str:
        """
        Create a persistent dashboard from a natural language request.

        Autonomously explores the database schema, designs the layout,
        generates valid SQL, and creates the dashboard.

        Args:
            request: Natural language description of the dashboard to create

        Returns:
            JSON string with success, dashboard_id, message, and steps
        """
        result = await invoke_dashboard_agent(request, context, SessionLocal)
        return json.dumps(result)

    return [dashboard_agent]


def build_analyze_dashboard_tool(context: AgentContext, db_session_factory: Optional[Callable] = None) -> List:
    """Return [analyze_dashboard] tool bound to context."""
    from backend.agents.orchestrator.orchestrator_dashboard_tools import build_dashboard_tools
    tools = build_dashboard_tools(context, db_session_factory)
    return [t for t in tools if getattr(t, "name", None) == "analyze_dashboard"]


def _build_communication_tools(context: AgentContext) -> List:
    """Return communication tools for the agent mesh."""
    from backend.agents.communication_tools import build_communication_tools
    from backend.services.agent_registry import AgentRegistry
    from backend.services.agent_message_bus import AgentMessageBus
    from backend.database.session import SessionLocal

    if not context.session_id:
        return []
    db = SessionLocal()
    registry = AgentRegistry()
    message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)
    return build_communication_tools(
        user_id=context.user_id,
        session_id=context.session_id,
        message_bus=message_bus,
        registry=registry,
    )


# ---------------------------------------------------------------------------
# Plugin tool builders (populated by plugin loader at startup)
# ---------------------------------------------------------------------------

_PLUGIN_TOOL_BUILDERS: Dict[str, Callable] = {}


def register_plugin_tool_builder(name: str, builder: Callable) -> None:
    """Register a tool builder provided by a plugin."""
    _PLUGIN_TOOL_BUILDERS[name] = builder


def get_plugin_tool_builders() -> Dict[str, Callable]:
    """Return a copy of all plugin-registered tool builders."""
    return dict(_PLUGIN_TOOL_BUILDERS)


TOOL_BUILDERS: Dict[str, Callable[[AgentContext], List]] = {
    "list_tables": build_list_tables_tool,
    "get_table_schema": build_get_table_schema_tool,
    "search_tables": build_search_tables_tool,
    "execute_query": build_execute_query_tool,
    "rag_search": _build_rag_search_tool,
    "recall_memory": _build_recall_memory_tool,
    "summarize_text": _build_summarize_tool,
    "create_dashboard": build_create_dashboard_tool,
    "analyze_dashboard": build_analyze_dashboard_tool,
    "dashboard_agent": _build_dashboard_agent_tool,
    "sessions_list": _build_communication_tools,
    "sessions_send": _build_communication_tools,
    "sessions_history": _build_communication_tools,
    "sessions_broadcast": _build_communication_tools,
}


def build_tools_for_keys(
    tool_keys: List[str],
    context: AgentContext,
    db_session_factory: Optional[Callable] = None,
) -> List:
    """Build LangChain tools for a list of allowed tool_keys.

    Merges core TOOL_BUILDERS with plugin-registered builders so that
    plugin tools (e.g. facebook_ads_summary) are resolved alongside
    built-in tools.
    """
    all_builders = {**TOOL_BUILDERS, **_PLUGIN_TOOL_BUILDERS}
    tools: List = []
    for key in tool_keys:
        builder = all_builders.get(key)
        if builder:
            try:
                sig = inspect.signature(builder)
                if "db_session_factory" in sig.parameters:
                    factory = db_session_factory
                    if factory is None:
                        from backend.database.session import SessionLocal
                        factory = SessionLocal
                    tools.extend(builder(context, factory))
                else:
                    tools.extend(builder(context))
            except Exception as exc:
                logger.warning(f"Failed to build tool '{key}': {exc}")
        else:
            logger.warning(f"Unknown tool_key '{key}' — skipping")
    return tools
