from langgraph.prebuilt import create_react_agent
from langgraph.errors import GraphRecursionError
from langchain_core.messages import HumanMessage, ToolMessage
from backend.agents.dashboard_agent.tools import build_dashboard_agent_tools
from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt
from backend.agents.profile_renderer import ProfileRenderer, RuntimeContext
from backend.agents.context import AgentContext
from backend.agents.data_agent.graph import _make_loop_detector
from backend.llm.factory import get_provider
from backend.config import settings
from typing import Dict, Any, Callable, List
import logging
import json

logger = logging.getLogger(__name__)


def _resolve_dashboard_agent_prompt(
    context: AgentContext,
    db_session_factory: Callable = None,
    target_connection_id: int | None = None,
    mesh_enabled: bool = False,
) -> str:
    """Resolve dashboard_agent prompt from profile or fallback to legacy."""
    if db_session_factory:
        try:
            db = db_session_factory()
            from backend.models.agent_profile import AgentProfile
            profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == context.user_id,
                AgentProfile.agent_type == "dashboard_agent",
                AgentProfile.is_active.is_(True),
            ).first()
            if profile:
                rt_ctx = RuntimeContext(
                    available_connections=context.available_connections,
                    connection_metadata=context.connection_metadata,
                    mesh_enabled=mesh_enabled or settings.agent_mesh_enabled,
                    target_connection_id=target_connection_id,
                )
                prompt = ProfileRenderer.render(profile, rt_ctx)
                db.close()
                return prompt
            db.close()
        except Exception as exc:
            logger.warning(f"Dashboard agent profile load failed, using legacy: {exc}")
    return build_dashboard_agent_prompt(
        context.available_connections,
        mesh_enabled=mesh_enabled,
        target_connection_id=target_connection_id,
        connection_metadata=context.connection_metadata,
    )


async def invoke_dashboard_agent(
    request: str,
    context: AgentContext,
    db_session_factory: Callable,
    target_connection_id: int | None = None,
) -> Dict[str, Any]:
    """
    Invoke Dashboard Agent for schema exploration and dashboard creation.

    When agent_mesh_enabled=True and context has a session_id, uses AgentRuntime
    for session-based execution with communication tools.

    Args:
        request: User's dashboard creation request
        context: AgentContext with user_id and available_connections
        db_session_factory: Callable returning a SQLAlchemy DB session
        target_connection_id: Pre-selected connection to focus on

    Returns:
        Dict with success, message, dashboard_id, steps
    """
    tools = build_dashboard_agent_tools(context, db_session_factory)

    # Use AgentRuntime when mesh is enabled for session-based execution
    if settings.agent_mesh_enabled and context.session_id:
        from backend.agents.runtime import AgentRuntime
        from backend.services.agent_registry import AgentRegistry
        from backend.services.agent_message_bus import AgentMessageBus

        registry = AgentRegistry()
        db = db_session_factory()
        message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)

        runtime = AgentRuntime(
            session_id=context.session_id,
            agent_type="dashboard_agent",
            user_id=context.user_id,
            context=context,
            registry=registry,
            message_bus=message_bus,
        )

        prompt = _resolve_dashboard_agent_prompt(context, db_session_factory, target_connection_id, mesh_enabled=True)
        result = await runtime.execute(request, tools, prompt)

        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "dashboard_id": None,  # Extracted from tool results
            "steps": [],
        }

    provider = get_provider(settings.default_llm_provider)

    agent = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=_resolve_dashboard_agent_prompt(context, db_session_factory, target_connection_id),
        pre_model_hook=_make_loop_detector(max_repeats=2, max_same_tool=15, max_total_calls=40),
    )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=request)]},
            config={"recursion_limit": settings.agent_recursion_limit},
        )

        messages = result.get("messages", [])
        dashboard_id, steps = _extract_results(messages)

        logger.info(
            "Dashboard agent completed in %d messages (limit: %d)",
            len(messages), settings.agent_recursion_limit,
        )

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

    except GraphRecursionError:
        logger.warning(
            "Dashboard agent hit recursion limit of %d",
            settings.agent_recursion_limit,
        )
        # The agent ran out of steps. Check if a dashboard was already
        # created during the partial run by querying the DB.
        partial_dashboard_id = _find_latest_dashboard(context.user_id, db_session_factory)
        if partial_dashboard_id:
            return {
                "success": True,
                "message": "Dashboard was created successfully, though the agent needed more steps than expected to finish.",
                "dashboard_id": partial_dashboard_id,
                "steps": [],
            }
        return {
            "success": False,
            "message": "The dashboard creation required too many steps. Try a simpler request with fewer widgets.",
            "dashboard_id": None,
            "steps": [],
        }

    except Exception as e:
        logger.exception("Dashboard agent failed")
        return {
            "success": False,
            "message": f"Dashboard agent failed: {type(e).__name__}: {e}" or "Dashboard agent failed: Unknown error",
            "dashboard_id": None,
            "steps": [],
        }


def _extract_results(messages: list) -> tuple:
    """Parse agent messages to extract dashboard_id and step trace."""
    dashboard_id = None
    steps: List[Dict] = []
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

            # Extract dashboard_id from create_dashboard or update_dashboard result
            if tool_name in ("create_dashboard", "update_dashboard") and isinstance(result_data, dict):
                if result_data.get("success") and result_data.get("dashboard_id"):
                    dashboard_id = result_data["dashboard_id"]

            steps.append({
                "agent_type": "dashboard_agent",
                "step_type": "tool_result",
                "tool_name": tool_name,
                "content": {"result": result_data},
            })

    return dashboard_id, steps


def _find_latest_dashboard(user_id: str, db_session_factory: Callable):
    """Check if a dashboard was created in the last 5 minutes by this user."""
    from datetime import datetime, timedelta, timezone
    from backend.models.dashboard import Dashboard

    db = db_session_factory()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        dashboard = (
            db.query(Dashboard)
            .filter(Dashboard.user_id == user_id, Dashboard.created_at >= cutoff)
            .order_by(Dashboard.created_at.desc())
            .first()
        )
        return dashboard.id if dashboard else None
    except Exception:
        return None
    finally:
        db.close()
