"""Tests for AgentRegistry service."""

import pytest
import fakeredis

from backend.services.agent_registry import AgentRegistry


@pytest.fixture
def mock_redis():
    """Fake Redis for unit tests."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def registry(mock_redis):
    return AgentRegistry(redis_client=mock_redis)


def test_register_session(registry, mock_redis):
    """Register creates Redis entry and adds to user's session set."""
    registry.register_session("user1", "s1", "data_agent")
    assert mock_redis.exists("agent:session:s1")
    assert mock_redis.sismember("agent:user_sessions:user1", "s1")


def test_register_session_data(registry, mock_redis):
    """Registered session has correct data fields."""
    registry.register_session(
        "user1", "s1", "data_agent",
        capabilities={"sql": True},
        metadata={"version": "1.0"},
    )
    data = mock_redis.hgetall("agent:session:s1")
    assert data["user_id"] == "user1"
    assert data["agent_type"] == "data_agent"
    assert data["status"] == "active"
    assert '"sql": true' in data["capabilities"]


def test_deregister_session(registry, mock_redis):
    """Deregister removes from both Redis key and user set."""
    registry.register_session("user1", "s1", "data_agent")
    registry.deregister_session("user1", "s1")
    assert not mock_redis.exists("agent:session:s1")
    assert not mock_redis.sismember("agent:user_sessions:user1", "s1")


def test_deregister_wrong_user_fails(registry):
    """Cannot deregister a session owned by another user."""
    registry.register_session("user1", "s1", "data_agent")
    with pytest.raises(PermissionError):
        registry.deregister_session("user2", "s1")


def test_heartbeat(registry, mock_redis):
    """Heartbeat updates timestamp and keeps session alive."""
    registry.register_session("user1", "s1", "data_agent")
    result = registry.heartbeat("s1")
    assert result is True
    data = mock_redis.hgetall("agent:session:s1")
    assert data["status"] == "active"


def test_heartbeat_nonexistent(registry):
    """Heartbeat on nonexistent session returns False."""
    result = registry.heartbeat("nonexistent")
    assert result is False


def test_get_session(registry):
    """Get session returns parsed data."""
    registry.register_session("user1", "s1", "data_agent", capabilities={"test": True})
    data = registry.get_session("s1")
    assert data is not None
    assert data["agent_type"] == "data_agent"
    assert data["capabilities"] == {"test": True}


def test_get_session_nonexistent(registry):
    """Get session returns None for nonexistent session."""
    assert registry.get_session("nonexistent") is None


def test_get_user_session_ids(registry):
    """Get all session IDs for a user."""
    registry.register_session("user1", "s1", "data_agent")
    registry.register_session("user1", "s2", "dashboard_agent")
    registry.register_session("user2", "s3", "data_agent")
    ids = registry.get_user_session_ids("user1")
    assert ids == {"s1", "s2"}


def test_update_status(registry, mock_redis):
    """Update session status."""
    registry.register_session("user1", "s1", "data_agent")
    registry.update_status("s1", "idle")
    data = mock_redis.hgetall("agent:session:s1")
    assert data["status"] == "idle"
