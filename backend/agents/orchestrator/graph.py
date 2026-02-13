from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from backend.agents.orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from backend.agents.data_agent import invoke_data_agent
from backend.agents.rag_agent import invoke_rag_agent
from backend.agents.skills import get_skill_registry
from backend.agents.context import AgentContext
from backend.llm.factory import get_llm_provider
from backend.config import settings
from typing import Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


def build_orchestrator_tools(context: AgentContext):
    """
    Build orchestrator tools with sub-agents as tools.

    Each sub-agent is wrapped as a tool that the orchestrator can invoke.
    Context is captured via closure for thread-safety.
    """

    @tool
    async def data_agent(question: str) -> str:
        """
        Query databases using SQL. Use for data analysis questions.

        Args:
            question: Natural language question about data

        Returns:
            JSON string with SQL queries and results
        """
        result = await invoke_data_agent(question, context)
        return json.dumps(result)

    @tool
    async def rag_agent(question: str, namespace: str = "default") -> str:
        """
        Search uploaded documents. Use for questions about documentation.

        Args:
            question: Question about documents
            namespace: Vector namespace (default: "default")

        Returns:
            JSON string with answer and source context
        """
        result = await invoke_rag_agent(question, context, namespace)
        return json.dumps(result)

    @tool
    async def recall_memory(query: str) -> str:
        """
        Recall past conversation context (Phase 06 - currently stub).

        Args:
            query: What to recall from memory

        Returns:
            JSON string with recalled context
        """
        result = {
            "success": False,
            "message": "Memory system not yet implemented (Phase 06)",
            "past_results": None
        }
        return json.dumps(result)

    # Get skills from registry
    skill_tools = get_skill_registry().to_tools()

    # Combine sub-agent tools + skill tools
    return [data_agent, rag_agent, recall_memory] + skill_tools


async def run_orchestrator(
    user_question: str,
    context: AgentContext
) -> Dict[str, Any]:
    """
    Run orchestrator agent (non-streaming).

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id

    Returns:
        Dict with success, message, metadata
    """
    # Build tools with captured context
    tools = build_orchestrator_tools(context)

    # Get LLM provider
    provider = get_llm_provider(settings.default_llm_provider)

    # Create orchestrator with memory
    memory = MemorySaver()
    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        checkpointer=memory,
        state_modifier=ORCHESTRATOR_SYSTEM_PROMPT
    )

    try:
        # Invoke with thread_id for conversation memory
        config = {"configurable": {"thread_id": context.thread_id or "default"}}

        result = await orchestrator.ainvoke(
            {"messages": [HumanMessage(content=user_question)]},
            config=config
        )

        # Extract final answer
        messages = result.get("messages", [])

        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not hasattr(msg, "tool_calls"):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Query completed successfully",
            "thread_id": context.thread_id
        }

    except Exception as e:
        logger.error(f"Orchestrator failed: {str(e)}")
        return {
            "success": False,
            "message": f"Orchestrator failed: {str(e)}",
            "thread_id": context.thread_id
        }


async def stream_orchestrator(
    user_question: str,
    context: AgentContext
):
    """
    Stream orchestrator responses (simplified version).

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id

    Yields:
        Chunks of the response
    """
    # For now, just run non-streaming and yield the result
    # Full streaming implementation would use astream_events
    result = await run_orchestrator(user_question, context)
    yield json.dumps(result)
