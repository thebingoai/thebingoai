"""Tests for AgentRuntime."""

import json
import pytest
import fakeredis
from unittest import mock
from unittest.mock import AsyncMock

from backend.agents.context import AgentContext
from backend.agents.runtime import AgentRuntime
from backend.services.agent_registry import AgentRegistry
from backend.services.agent_message_bus import AgentMessageBus


@pytest.fixture
def mock_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def registry(mock_redis):
    return AgentRegistry(redis_client=mock_redis)


@pytest.fixture
def message_bus(mock_redis):
    return AgentMessageBus(db_session=None, redis_client=mock_redis)


@pytest.fixture
def agent_context():
    return AgentContext(
        user_id="test-user-1",
        available_connections=[1, 2],
        session_id="test-session-001",
    )


@pytest.fixture
def runtime(agent_context, registry, message_bus):
    # Register the session so drain_inbox doesn't fail
    registry.register_session("test-user-1", "test-session-001", "data_agent")
    return AgentRuntime(
        session_id="test-session-001",
        agent_type="data_agent",
        user_id="test-user-1",
        context=agent_context,
        registry=registry,
        message_bus=message_bus,
    )


@pytest.mark.asyncio
async def test_runtime_registers_session(runtime, mock_redis):
    """AgentRuntime.execute registers session on start."""
    with mock.patch("langgraph.prebuilt.create_react_agent") as mock_agent:
        mock_result = {"messages": [mock.MagicMock(type="ai", content="done", tool_calls=None)]}
        mock_agent.return_value.ainvoke = AsyncMock(return_value=mock_result)
        with mock.patch("backend.llm.factory.get_provider"):
            result = await runtime.execute("test", tools=[], system_prompt="test")
    assert mock_redis.exists("agent:session:test-session-001")
    assert result["success"] is True


@pytest.mark.asyncio
async def test_runtime_injects_communication_tools(runtime):
    """AgentRuntime adds sessions_list, sessions_send, etc. to tool list."""
    comm_tools = runtime.build_communication_tools()
    tool_names = [t.name for t in comm_tools]
    assert "sessions_list" in tool_names
    assert "sessions_send" in tool_names
    assert "sessions_history" in tool_names
    assert "sessions_broadcast" in tool_names


@pytest.mark.asyncio
async def test_runtime_drains_inbox_on_execute(runtime, mock_redis):
    """AgentRuntime processes pending inbox messages before executing."""
    mock_redis.rpush(
        "agent:inbox:test-session-001",
        json.dumps({"from_session_id": "s2", "content": {"text": "pending msg"}}),
    )
    with mock.patch("langgraph.prebuilt.create_react_agent") as mock_agent:
        mock_result = {"messages": [mock.MagicMock(type="ai", content="done", tool_calls=None)]}
        mock_agent.return_value.ainvoke = AsyncMock(return_value=mock_result)
        with mock.patch("backend.llm.factory.get_provider"):
            await runtime.execute("test", tools=[], system_prompt="test")
    assert mock_redis.llen("agent:inbox:test-session-001") == 0


@pytest.mark.asyncio
async def test_runtime_handles_execution_failure(runtime):
    """AgentRuntime returns failure dict on exception."""
    with mock.patch("langgraph.prebuilt.create_react_agent") as mock_agent:
        mock_agent.return_value.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        with mock.patch("backend.llm.factory.get_provider"):
            result = await runtime.execute("test", tools=[], system_prompt="test")
    assert result["success"] is False
    assert "LLM error" in result["message"]
