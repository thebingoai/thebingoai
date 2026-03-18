"""Monitor Agent graph — autonomous background agent for anomaly detection."""

from typing import Dict, Any
import logging

from backend.agents.context import AgentContext
from backend.agents.monitor_agent.tools import build_monitor_agent_tools
from backend.agents.monitor_agent.prompts import MONITOR_AGENT_SYSTEM_PROMPT
from backend.config import settings

logger = logging.getLogger(__name__)


async def invoke_monitor_agent(
    prompt: str,
    context: AgentContext,
) -> Dict[str, Any]:
    """
    Invoke the Monitor Agent.

    When mesh is enabled, uses AgentRuntime for session-based execution
    with communication tools for coordinating with data_agent.

    Args:
        prompt: The monitoring task/query
        context: AgentContext with user_id and available_connections

    Returns:
        Dict with success, message, findings
    """
    tools = build_monitor_agent_tools(context)

    if settings.agent_mesh_enabled and context.session_id:
        from backend.agents.runtime import AgentRuntime
        from backend.services.agent_registry import AgentRegistry
        from backend.services.agent_message_bus import AgentMessageBus
        from backend.database.session import SessionLocal

        registry = AgentRegistry()
        db = SessionLocal()
        message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)

        runtime = AgentRuntime(
            session_id=context.session_id,
            agent_type="monitor_agent",
            user_id=context.user_id,
            context=context,
            registry=registry,
            message_bus=message_bus,
        )

        result = await runtime.execute(prompt, tools, MONITOR_AGENT_SYSTEM_PROMPT)
        return result

    # Fallback: inline execution without mesh
    from langgraph.prebuilt import create_react_agent
    from langchain_core.messages import HumanMessage
    from backend.llm.factory import get_provider

    provider = get_provider(settings.default_llm_provider)

    agent = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=MONITOR_AGENT_SYSTEM_PROMPT,
    )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=prompt)]},
        )

        messages = result.get("messages", [])
        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Monitoring completed",
        }

    except Exception as e:
        logger.error(f"Monitor agent failed: {e}")
        return {
            "success": False,
            "message": f"Monitor agent failed: {e}",
        }
