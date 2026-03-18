"""Tests for AgentSession and AgentMessage ORM models."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.agent_session import AgentSession
from backend.models.agent_message import AgentMessage

# Tables needed for these tests (avoid creating all tables which
# may have Postgres-specific types like JSONB that fail on SQLite)
_TABLES = [
    User.__table__,
    AgentSession.__table__,
    AgentMessage.__table__,
]


@pytest.fixture
def test_db():
    """In-memory SQLite with agent mesh tables only."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_TABLES)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(email="agent-test@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user, test_db


@pytest.fixture
def second_user(test_db):
    """Create a second user for isolation tests."""
    user = User(email="other@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user


def test_create_agent_session(test_user):
    """AgentSession is created with correct user ownership."""
    user, db = test_user
    session = AgentSession(user_id=user.id, agent_type="data_agent", status="active")
    db.add(session)
    db.commit()
    assert session.id is not None
    assert session.user_id == user.id
    assert session.status == "active"
    assert session.agent_type == "data_agent"


def test_create_agent_message(test_user):
    """AgentMessage links two sessions for the same user."""
    user, db = test_user
    s1 = AgentSession(user_id=user.id, agent_type="orchestrator", status="active")
    s2 = AgentSession(user_id=user.id, agent_type="data_agent", status="active")
    db.add_all([s1, s2])
    db.commit()
    msg = AgentMessage(
        user_id=user.id,
        from_session_id=s1.id,
        to_session_id=s2.id,
        message_type="request",
        content={"text": "list tables"},
        status="pending",
    )
    db.add(msg)
    db.commit()
    assert msg.id is not None
    assert msg.user_id == user.id
    assert msg.from_session_id == s1.id
    assert msg.to_session_id == s2.id


def test_agent_session_user_relationship(test_user):
    """User's agent sessions are accessible via relationship."""
    user, db = test_user
    db.add(AgentSession(user_id=user.id, agent_type="data_agent", status="active"))
    db.add(AgentSession(user_id=user.id, agent_type="dashboard_agent", status="active"))
    db.commit()
    db.refresh(user)
    assert len(user.agent_sessions) == 2


def test_agent_session_with_capabilities(test_user):
    """AgentSession stores JSON capabilities."""
    user, db = test_user
    session = AgentSession(
        user_id=user.id,
        agent_type="data_agent",
        status="active",
        capabilities={"sql": True, "schema_discovery": True},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    assert session.capabilities["sql"] is True


def test_agent_session_default_status(test_user):
    """AgentSession defaults to 'active' status."""
    user, db = test_user
    session = AgentSession(user_id=user.id, agent_type="rag_agent")
    db.add(session)
    db.commit()
    assert session.status == "active"


def test_agent_message_correlation_id(test_user):
    """AgentMessage supports correlation_id for request/response pairing."""
    user, db = test_user
    s1 = AgentSession(user_id=user.id, agent_type="orchestrator", status="active")
    s2 = AgentSession(user_id=user.id, agent_type="data_agent", status="active")
    db.add_all([s1, s2])
    db.commit()

    msg = AgentMessage(
        user_id=user.id,
        from_session_id=s1.id,
        to_session_id=s2.id,
        message_type="request",
        content={"text": "hello"},
        correlation_id="corr-123",
        status="pending",
    )
    db.add(msg)
    db.commit()
    assert msg.correlation_id == "corr-123"
