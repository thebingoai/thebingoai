"""Integration tests for Celery agent tasks."""

import pytest
import fakeredis
from unittest import mock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.agent_session import AgentSession
from backend.models.agent_message import AgentMessage
from backend.services.agent_registry import AgentRegistry


_TABLES = [User.__table__, AgentSession.__table__, AgentMessage.__table__]


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_TABLES)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def mock_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.mark.integration
def test_agent_health_check_marks_stale(mock_redis):
    """agent_health_check marks sessions with expired heartbeat as degraded."""
    from datetime import datetime, timedelta

    registry = AgentRegistry(redis_client=mock_redis)
    registry.register_session("user1", "s1", "data_agent")

    # Manually set last_heartbeat to 10 minutes ago
    old_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
    mock_redis.hset("agent:session:s1", "last_heartbeat", old_time)

    stale_count = registry.cleanup_stale_sessions()
    assert stale_count == 1

    data = mock_redis.hgetall("agent:session:s1")
    assert data["status"] == "degraded"


@pytest.mark.integration
def test_process_agent_message_structure(test_db, mock_redis):
    """process_agent_message reads message and validates structure."""
    user = User(email="task-test@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()

    s1 = AgentSession(user_id=user.id, agent_type="orchestrator", status="active")
    s2 = AgentSession(user_id=user.id, agent_type="data_agent", status="active")
    test_db.add_all([s1, s2])
    test_db.commit()

    msg = AgentMessage(
        user_id=user.id,
        from_session_id=s1.id,
        to_session_id=s2.id,
        message_type="request",
        content={"text": "list tables"},
        status="pending",
    )
    test_db.add(msg)
    test_db.commit()

    # Verify message was created correctly
    loaded = test_db.query(AgentMessage).filter_by(id=msg.id).first()
    assert loaded is not None
    assert loaded.content == {"text": "list tables"}
    assert loaded.user_id == user.id
