"""
Tool Registry — maps tool_key strings (stored in DB) to Python tool-builder functions.

Each builder receives an AgentContext and returns a list of LangChain tools.
New tools are registered here by adding an entry to TOOL_BUILDERS.
"""
from typing import Dict, Callable, List
from backend.agents.context import AgentContext
from backend.agents.data_agent.tools import (
    build_list_tables_tool,
    build_get_table_schema_tool,
    build_search_tables_tool,
    build_execute_query_tool,
)
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

TOOL_BUILDERS: Dict[str, Callable[[AgentContext], List]] = {
    "list_tables": build_list_tables_tool,
    "get_table_schema": build_get_table_schema_tool,
    "search_tables": build_search_tables_tool,
    "execute_query": build_execute_query_tool,
    "rag_search": _build_rag_search_tool,
    "recall_memory": _build_recall_memory_tool,
    "summarize_text": _build_summarize_tool,
}


def build_tools_for_keys(tool_keys: List[str], context: AgentContext) -> List:
    """Build LangChain tools for a list of allowed tool_keys."""
    tools: List = []
    for key in tool_keys:
        builder = TOOL_BUILDERS.get(key)
        if builder:
            try:
                tools.extend(builder(context))
            except Exception as exc:
                logger.warning(f"Failed to build tool '{key}': {exc}")
        else:
            logger.warning(f"Unknown tool_key '{key}' — skipping")
    return tools
