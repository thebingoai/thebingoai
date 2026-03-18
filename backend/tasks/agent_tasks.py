"""
Celery tasks for agent mesh operations.

- run_agent_session: Execute an agent within its session context
- process_agent_message: Handle incoming inter-agent messages
- agent_health_check: Periodic task to detect stale sessions
"""

import asyncio
import json
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="run_agent_session", time_limit=300)
def run_agent_session(session_id: str, message: str, context_dict: dict) -> dict:
    """
    Execute an agent session.

    Args:
        session_id: Agent session ID
        message: Input message to process
        context_dict: Serialized AgentContext fields

    Returns:
        Dict with success, message, session_id
    """
    from backend.agents.context import AgentContext
    from backend.agents.runtime import AgentRuntime
    from backend.services.agent_registry import AgentRegistry
    from backend.services.agent_message_bus import AgentMessageBus
    from backend.database.session import SessionLocal

    db = SessionLocal()
    try:
        registry = AgentRegistry()
        message_bus = AgentMessageBus(db_session=db)

        # Reconstruct context
        context = AgentContext(
            user_id=context_dict["user_id"],
            available_connections=context_dict.get("available_connections", []),
            thread_id=context_dict.get("thread_id"),
            team_id=context_dict.get("team_id"),
            allowed_tool_keys=context_dict.get("allowed_tool_keys", []),
            session_id=context_dict.get("session_id"),
        )

        # Look up session to get agent_type
        session_data = registry.get_session(session_id)
        if not session_data:
            return {"success": False, "message": f"Session {session_id} not found"}

        agent_type = session_data.get("agent_type", "unknown")

        # Build agent-specific tools and prompt
        tools, prompt = _build_agent_config(agent_type, context, db)

        runtime = AgentRuntime(
            session_id=session_id,
            agent_type=agent_type,
            user_id=context.user_id,
            context=context,
            registry=registry,
            message_bus=message_bus,
        )

        result = asyncio.run(runtime.execute(message, tools, prompt))
        return result

    except Exception as e:
        logger.error("run_agent_session failed (session=%s): %s", session_id, e, exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        db.close()


@shared_task(name="process_agent_message", time_limit=120)
def process_agent_message(message_id: str) -> dict:
    """
    Process an inter-agent message by dispatching the target agent session.

    Args:
        message_id: AgentMessage ID to process

    Returns:
        Dict with success status
    """
    from backend.models.agent_message import AgentMessage
    from backend.database.session import SessionLocal
    from backend.services.agent_registry import AgentRegistry

    db = SessionLocal()
    try:
        msg = db.query(AgentMessage).filter(AgentMessage.id == message_id).first()
        if not msg:
            return {"success": False, "message": f"Message {message_id} not found"}

        # Validate user owns both sessions
        registry = AgentRegistry()
        to_session = registry.get_session(msg.to_session_id)
        if not to_session:
            return {"success": False, "message": f"Target session {msg.to_session_id} not found"}

        if to_session.get("user_id") != msg.user_id:
            return {"success": False, "message": "Cross-user message rejected"}

        # Dispatch run_agent_session for the target
        context_dict = {
            "user_id": msg.user_id,
            "available_connections": [],
            "session_id": msg.to_session_id,
        }

        content = msg.content or {}
        text = content.get("text", json.dumps(content))

        run_agent_session.delay(msg.to_session_id, text, context_dict)

        # Mark message as delivered
        msg.status = "delivered"
        db.commit()

        return {"success": True, "dispatched_to": msg.to_session_id}

    except Exception as e:
        logger.error("process_agent_message failed (msg=%s): %s", message_id, e, exc_info=True)
        return {"success": False, "message": str(e)}
    finally:
        db.close()


@shared_task(name="agent_health_check")
def agent_health_check() -> dict:
    """
    Periodic task: check agent session health, mark stale sessions as degraded.
    Runs via Celery Beat.
    """
    from backend.services.agent_registry import AgentRegistry

    try:
        registry = AgentRegistry()
        stale_count = registry.cleanup_stale_sessions()
        logger.info("Agent health check: marked %d stale sessions", stale_count)
        return {"success": True, "stale_sessions_marked": stale_count}
    except Exception as e:
        logger.error("agent_health_check failed: %s", e, exc_info=True)
        return {"success": False, "message": str(e)}


def _build_agent_config(agent_type: str, context, db_session) -> tuple:
    """
    Build tools and system prompt for a given agent type.

    Returns:
        (tools_list, system_prompt_string)
    """
    if agent_type == "data_agent":
        from backend.agents.data_agent.tools import build_data_agent_tools
        from backend.agents.data_agent.prompts import build_data_agent_prompt

        tools = build_data_agent_tools(context)
        prompt = build_data_agent_prompt(context.available_connections)
        return tools, prompt

    elif agent_type == "dashboard_agent":
        from backend.agents.dashboard_agent.tools import build_dashboard_agent_tools
        from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt

        tools = build_dashboard_agent_tools(context, lambda: db_session)
        prompt = build_dashboard_agent_prompt(context.available_connections)
        return tools, prompt

    elif agent_type == "rag_agent":
        from backend.agents.tool_registry import _build_rag_search_tool

        tools = _build_rag_search_tool(context)
        prompt = "You are a document search agent. Use the rag_search tool to answer questions about uploaded documents."
        return tools, prompt

    else:
        # Custom or unknown agent — try to load from DB
        from backend.models.custom_agent import CustomAgent
        from backend.agents.tool_registry import build_tools_for_keys

        custom = (
            db_session.query(CustomAgent)
            .filter(
                CustomAgent.user_id == context.user_id,
                CustomAgent.is_active == True,
            )
            .first()
        )
        if custom:
            tools = build_tools_for_keys(custom.tool_keys or [], context)
            return tools, custom.system_prompt
        return [], f"You are a {agent_type} agent."
