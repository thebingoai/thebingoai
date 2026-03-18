"""Integration tests for agent sessions REST API."""

import pytest
import fakeredis
from unittest import mock

from backend.services.agent_registry import AgentRegistry
from backend.services.agent_discovery import AgentDiscovery


@pytest.fixture
def mock_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.mark.integration
def test_list_sessions_returns_user_sessions(mock_redis):
    """GET /api/agent-sessions returns only authenticated user's sessions."""
    registry = AgentRegistry(redis_client=mock_redis)

    # Create sessions for two users
    registry.register_session("user-a", "sa1", "orchestrator")
    registry.register_session("user-a", "sa2", "data_agent")
    registry.register_session("user-b", "sb1", "orchestrator")

    discovery = AgentDiscovery(redis_client=mock_redis)
    a_sessions = discovery.list_sessions("user-a")
    b_sessions = discovery.list_sessions("user-b")

    assert len(a_sessions) == 2
    assert len(b_sessions) == 1


@pytest.mark.integration
def test_session_ownership_validation(mock_redis):
    """get_session validates user ownership."""
    registry = AgentRegistry(redis_client=mock_redis)
    registry.register_session("user-a", "sa1", "orchestrator")

    discovery = AgentDiscovery(redis_client=mock_redis)

    # User A can see their session
    session = discovery.get_session("user-a", "sa1")
    assert session["agent_type"] == "orchestrator"

    # User B cannot
    with pytest.raises(PermissionError):
        discovery.get_session("user-b", "sa1")


@pytest.mark.integration
def test_terminate_session(mock_redis):
    """DELETE deregisters the session."""
    registry = AgentRegistry(redis_client=mock_redis)
    registry.register_session("user-a", "sa1", "orchestrator")

    registry.deregister_session("user-a", "sa1")

    assert not mock_redis.exists("agent:session:sa1")
    assert not mock_redis.sismember("agent:user_sessions:user-a", "sa1")
