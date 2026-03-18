"""Tests for AgentDiscovery service."""

import pytest
import fakeredis

from backend.services.agent_registry import AgentRegistry
from backend.services.agent_discovery import AgentDiscovery


@pytest.fixture
def mock_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def registry(mock_redis):
    return AgentRegistry(redis_client=mock_redis)


@pytest.fixture
def discovery(mock_redis):
    return AgentDiscovery(redis_client=mock_redis)


def test_list_sessions_user_scoped(registry, discovery):
    """list_sessions only returns sessions for the specified user."""
    registry.register_session("user1", "s1", "data_agent")
    registry.register_session("user2", "s2", "data_agent")
    sessions = discovery.list_sessions("user1")
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "s1"


def test_list_sessions_filter_type(registry, discovery):
    """list_sessions filters by agent_type."""
    registry.register_session("user1", "s1", "data_agent")
    registry.register_session("user1", "s2", "dashboard_agent")
    sessions = discovery.list_sessions("user1", filter_type="data_agent")
    assert len(sessions) == 1
    assert sessions[0]["agent_type"] == "data_agent"


def test_list_sessions_excludes_terminated(registry, discovery, mock_redis):
    """list_sessions excludes terminated sessions."""
    registry.register_session("user1", "s1", "data_agent")
    registry.update_status("s1", "terminated")
    sessions = discovery.list_sessions("user1")
    assert len(sessions) == 0


def test_find_session_by_type(registry, discovery):
    """find_session_by_type returns matching agent for user."""
    registry.register_session("user1", "s1", "data_agent")
    registry.register_session("user1", "s2", "dashboard_agent")
    result = discovery.find_session_by_type("user1", "data_agent")
    assert result is not None
    assert result["agent_type"] == "data_agent"


def test_find_session_by_type_not_found(registry, discovery):
    """find_session_by_type returns None when no match."""
    registry.register_session("user1", "s1", "data_agent")
    result = discovery.find_session_by_type("user1", "rag_agent")
    assert result is None


def test_get_session_validates_ownership(registry, discovery):
    """get_session for wrong user raises PermissionError."""
    registry.register_session("user1", "s1", "data_agent")
    with pytest.raises(PermissionError):
        discovery.get_session("user2", "s1")


def test_get_session_not_found(registry, discovery):
    """get_session for nonexistent session raises ValueError."""
    # Add s1 to user set but don't create the hash
    discovery.redis.sadd("agent:user_sessions:user1", "s999")
    with pytest.raises(ValueError):
        discovery.get_session("user1", "s999")


def test_find_session_prefers_active(registry, discovery, mock_redis):
    """find_session_by_type prefers active over idle."""
    registry.register_session("user1", "s1", "data_agent")
    registry.register_session("user1", "s2", "data_agent")
    registry.update_status("s1", "idle")
    result = discovery.find_session_by_type("user1", "data_agent")
    assert result["session_id"] == "s2"
    assert result["status"] == "active"
