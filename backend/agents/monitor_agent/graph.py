"""Monitor Agent graph — autonomous background agent for anomaly detection."""

from typing import Dict, Any
import logging

from backend.agents.context import AgentContext
from backend.agents.invoke_helpers import extract_final_answer, run_inline_react, run_via_mesh_runtime
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
    """
    tools = build_monitor_agent_tools(context)

    if settings.agent_mesh_enabled and context.session_id:
        return await run_via_mesh_runtime(
            agent_type="monitor_agent",
            user_id=context.user_id,
            session_id=context.session_id,
            context=context,
            message=prompt,
            tools=tools,
            system_prompt=MONITOR_AGENT_SYSTEM_PROMPT,
        )

    try:
        messages = await run_inline_react(
            tools=tools,
            system_prompt=MONITOR_AGENT_SYSTEM_PROMPT,
            message=prompt,
            agent_type="monitor_agent",
            user_id=getattr(context, "user_id", None),
            session_id=getattr(context, "session_id", None),
        )
        return {
            "success": True,
            "message": extract_final_answer(messages) or "Monitoring completed",
        }
    except Exception as e:
        logger.error(f"Monitor agent failed: {e}")
        return {
            "success": False,
            "message": f"Monitor agent failed: {e}",
        }
