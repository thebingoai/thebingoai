"""Shared helpers for agent invocation.

Extracted from invoke_data_agent / invoke_dashboard_agent / invoke_monitor_agent
and the orchestrator, which all duplicated:

1. The "find the last AI message without tool calls" pattern.
2. The mesh-vs-inline branch (AgentRuntime path vs direct create_react_agent path).
"""
from typing import Any, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage


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

    runtime = AgentRuntime(
        session_id=session_id,
        agent_type=agent_type,
        user_id=user_id,
        context=context,
        registry=registry,
        message_bus=message_bus,
    )
    return await runtime.execute(message, tools, system_prompt)


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
    return result.get("messages", [])
