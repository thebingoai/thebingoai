from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, ToolMessage
from backend.agents.dashboard_agent.tools import build_dashboard_agent_tools
from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt
from backend.agents.context import AgentContext
from backend.llm.factory import get_provider
from backend.config import settings
from typing import Dict, Any, Callable
import logging
import json

logger = logging.getLogger(__name__)


async def invoke_dashboard_agent(
    request: str,
    context: AgentContext,
    db_session_factory: Callable,
) -> Dict[str, Any]:
    """
    Invoke stateless Dashboard Agent for schema exploration and dashboard creation.

    Args:
        request: User's dashboard creation request
        context: AgentContext with user_id and available_connections
        db_session_factory: Callable returning a SQLAlchemy DB session

    Returns:
        Dict with success, message, dashboard_id, steps
    """
    tools = build_dashboard_agent_tools(context, db_session_factory)

    provider = get_provider(settings.default_llm_provider)

    agent = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=build_dashboard_agent_prompt(context.available_connections),
    )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=request)]}
        )

        messages = result.get("messages", [])
        dashboard_id = None
        steps = []

        tool_call_index: Dict[str, Dict] = {}

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name")
                    args = tool_call.get("args", {})
                    tool_call_id = tool_call.get("id", "")

                    tool_call_index[tool_call_id] = {"name": tool_name, "args": args}

                    steps.append({
                        "agent_type": "dashboard_agent",
                        "step_type": "tool_call",
                        "tool_name": tool_name,
                        "content": {"args": args},
                    })

            elif isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", "")
                call_info = tool_call_index.get(tool_call_id, {})
                tool_name = call_info.get("name", "unknown")

                result_data = None
                if isinstance(msg.content, str):
                    try:
                        result_data = json.loads(msg.content)
                    except (json.JSONDecodeError, TypeError):
                        result_data = msg.content
                else:
                    result_data = msg.content

                # Extract dashboard_id from create_dashboard result
                if tool_name == "create_dashboard" and isinstance(result_data, dict):
                    if result_data.get("success") and result_data.get("dashboard_id"):
                        dashboard_id = result_data["dashboard_id"]

                steps.append({
                    "agent_type": "dashboard_agent",
                    "step_type": "tool_result",
                    "tool_name": tool_name,
                    "content": {"result": result_data},
                })

        # Get final answer (last AI message without tool calls)
        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Dashboard creation completed.",
            "dashboard_id": dashboard_id,
            "steps": steps,
        }

    except Exception as e:
        logger.error(f"Dashboard agent failed: {str(e)}")
        return {
            "success": False,
            "message": f"Dashboard agent failed: {str(e)}",
            "dashboard_id": None,
            "steps": [],
        }
