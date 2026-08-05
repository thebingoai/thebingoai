"""Shared helpers for agent invocation.

Extracted from invoke_data_agent / invoke_dashboard_agent / invoke_monitor_agent
and the orchestrator, which all duplicated:

1. The "find the last AI message without tool calls" pattern.
2. The mesh-vs-inline branch (AgentRuntime path vs direct create_react_agent path).
"""
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


def extract_final_answer(messages: list) -> Optional[str]:
    """Return the last AIMessage content without tool calls — the assistant's final textual answer."""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
            return msg.content
    return None


async def run_via_mesh_runtime(
    *,
    agent_type: str,
    user_id: str,
    session_id: str,
    context,
    message: str,
    tools: list,
    system_prompt: str,
    db_session_factory: Optional[Callable] = None,
) -> dict:
    """Mesh path: register a session, drain inbox, execute via AgentRuntime.

    Returns AgentRuntime.execute's result dict directly: {success, message, session_id}.
    """
    from backend.agents.runtime import AgentRuntime
    from backend.services.agent_registry import AgentRegistry
    from backend.services.agent_message_bus import AgentMessageBus

    registry = AgentRegistry()
    if db_session_factory is not None:
        db = db_session_factory()
    else:
        from backend.database.session import SessionLocal
        db = SessionLocal()
    message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)

    # The session must outlive nothing here: the message bus is local to this
    # call, so close it on the way out. Without this the checkout leaks on every
    # mesh invocation and the pool drains.
    try:
        runtime = AgentRuntime(
            session_id=session_id,
            agent_type=agent_type,
            user_id=user_id,
            context=context,
            registry=registry,
            message_bus=message_bus,
        )
        return await runtime.execute(message, tools, system_prompt)
    finally:
        db.close()


async def run_inline_react(
    *,
    tools: list,
    system_prompt: str,
    message: str,
    llm_provider=None,
    pre_model_hook=None,
    recursion_limit: Optional[int] = None,
    agent_type: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> List[Any]:
    """Inline path: create a stateless ReAct agent and invoke it once.

    Returns the raw list of messages (caller decides how to extract results).
    """
    from langgraph.prebuilt import create_react_agent

    from backend.config import settings
    from backend.llm.factory import get_provider
    from backend.agents.callbacks import get_callbacks

    provider = llm_provider or get_provider(settings.default_llm_provider)
    kwargs = {
        "model": provider.get_langchain_llm(),
        "tools": tools,
        "prompt": system_prompt,
    }
    if pre_model_hook is not None:
        kwargs["pre_model_hook"] = pre_model_hook

    agent = create_react_agent(**kwargs)
    _t0 = time.perf_counter()
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        config={
            "recursion_limit": recursion_limit or settings.agent_recursion_limit,
            "callbacks": get_callbacks(
                agent_type=agent_type,
                session_id=session_id,
                user_id=user_id,
            ),
        },
    )
    logger.info(
        "[LATENCY][%s] LLM ainvoke total: %dms",
        agent_type or "sub_agent",
        int((time.perf_counter() - _t0) * 1000),
    )
    return result.get("messages", [])
