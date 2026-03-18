"""Tests for inter-agent communication tools."""

import json
import pytest
import fakeredis

from backend.agents.communication_tools import build_communication_tools
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
def setup_agents(registry):
    """Register orchestrator, data_agent, dashboard_agent for user1."""
    registry.register_session("user1", "orch-1", "orchestrator")
    registry.register_session("user1", "data-1", "data_agent")
    registry.register_session("user1", "dash-1", "dashboard_agent")
    registry.register_session("user2", "data-2", "data_agent")


@pytest.fixture
def tools(setup_agents, message_bus, registry):
    """Build communication tools for user1's orchestrator."""
    return build_communication_tools(
        user_id="user1",
        session_id="orch-1",
        message_bus=message_bus,
        registry=registry,
    )


def _get_tool(tools, name):
    for t in tools:
        if t.name == name:
            return t
    raise ValueError(f"Tool {name} not found")


def test_sessions_list_returns_user_agents(tools):
    """sessions_list tool returns only the current user's active agents."""
    sessions_list = _get_tool(tools, "sessions_list")
    result = json.loads(sessions_list.invoke({"filter_type": ""}))
    assert len(result) == 3  # orchestrator, data_agent, dashboard_agent
    agent_types = {s["agent_type"] for s in result}
    assert "data_agent" in agent_types
    assert "dashboard_agent" in agent_types


def test_sessions_list_filter_type(tools):
    """sessions_list with filter_type returns only matching agents."""
    sessions_list = _get_tool(tools, "sessions_list")
    result = json.loads(sessions_list.invoke({"filter_type": "data_agent"}))
    assert len(result) == 1
    assert result[0]["agent_type"] == "data_agent"


def test_sessions_send_same_user(tools, mock_redis):
    """sessions_send delivers message to another agent of the same user."""
    sessions_send = _get_tool(tools, "sessions_send")
    result = json.loads(
        sessions_send.invoke({
            "to_session_id": "data-1",
            "message": "list tables",
            "wait_for_response": False,
        })
    )
    assert result["success"] is True
    assert mock_redis.llen("agent:inbox:data-1") == 1


def test_sessions_send_cross_user_blocked(tools, mock_redis):
    """sessions_send rejects targeting a session owned by a different user."""
    sessions_send = _get_tool(tools, "sessions_send")
    # data-2 belongs to user2, but tool is built for user1
    # The PermissionError propagates through LangChain's tool invocation
    with pytest.raises(Exception):
        sessions_send.invoke({
            "to_session_id": "data-2",
            "message": "test",
            "wait_for_response": False,
        })
    # Verify the inbox was NOT written to
    assert mock_redis.llen("agent:inbox:data-2") == 0


def test_sessions_broadcast(tools, mock_redis):
    """sessions_broadcast sends to all of user's agents except sender."""
    sessions_broadcast = _get_tool(tools, "sessions_broadcast")
    result = json.loads(
        sessions_broadcast.invoke({"message": "alert!", "filter_type": ""})
    )
    assert result["success"] is True
    assert result["messages_sent"] == 2  # data-1 and dash-1 (not orch-1)
    assert mock_redis.llen("agent:inbox:data-1") == 1
    assert mock_redis.llen("agent:inbox:dash-1") == 1
    assert mock_redis.llen("agent:inbox:orch-1") == 0


def test_sessions_history_empty(tools):
    """sessions_history returns empty when no messages."""
    sessions_history = _get_tool(tools, "sessions_history")
    result = json.loads(
        sessions_history.invoke({"session_id_filter": "", "limit": 20})
    )
    assert result == []
