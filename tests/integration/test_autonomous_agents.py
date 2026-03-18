"""Integration tests for autonomous background agents."""

import pytest
import fakeredis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.agent_session import AgentSession
from backend.models.heartbeat_job import HeartbeatJob
from backend.services.agent_registry import AgentRegistry
from backend.services.agent_discovery import AgentDiscovery


_TABLES = [User.__table__, AgentSession.__table__, HeartbeatJob.__table__]


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


@pytest.fixture
def test_user(test_db):
    user = User(email="auto-test@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user, test_db


@pytest.mark.integration
def test_heartbeat_job_with_agent_type(test_user):
    """HeartbeatJob supports agent_type for routing."""
    user, db = test_user
    job = HeartbeatJob(
        user_id=user.id,
        name="Monitor Revenue",
        prompt="Check revenue metrics",
        schedule_type="cron",
        schedule_value="0 * * * *",
        cron_expression="0 * * * *",
        agent_type="monitor_agent",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    assert job.agent_type == "monitor_agent"


@pytest.mark.integration
def test_heartbeat_job_default_agent_type(test_user):
    """HeartbeatJob defaults to None agent_type (orchestrator)."""
    user, db = test_user
    job = HeartbeatJob(
        user_id=user.id,
        name="Daily Summary",
        prompt="Summarize today",
        schedule_type="cron",
        schedule_value="0 0 * * *",
        cron_expression="0 0 * * *",
    )
    db.add(job)
    db.commit()
    assert job.agent_type is None


@pytest.mark.integration
def test_monitor_agent_session_creation(test_user, mock_redis):
    """Monitor agent creates a session when executed."""
    user, db = test_user
    registry = AgentRegistry(redis_client=mock_redis)

    import uuid
    session_id = str(uuid.uuid4())
    registry.register_session(user.id, session_id, "monitor_agent")

    discovery = AgentDiscovery(redis_client=mock_redis)
    found = discovery.find_session_by_type(user.id, "monitor_agent")
    assert found is not None
    assert found["agent_type"] == "monitor_agent"
