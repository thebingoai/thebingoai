"""Tests for user isolation in the agent mesh."""

import pytest
import fakeredis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.agent_session import AgentSession
from backend.models.agent_message import AgentMessage
from backend.services.agent_registry import AgentRegistry
from backend.services.agent_discovery import AgentDiscovery
from backend.services.agent_message_bus import AgentMessageBus


@pytest.fixture
def mock_redis():
    return fakeredis.FakeRedis(decode_responses=True)


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
def user_a(test_db):
    user = User(email="user-a@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_b(test_db):
    user = User(email="user-b@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def setup(user_a, user_b, test_db, mock_redis):
    """Create sessions for both users."""
    registry = AgentRegistry(redis_client=mock_redis)

    # User A: 3 agents
    sa1 = AgentSession(user_id=user_a.id, agent_type="orchestrator", status="active")
    sa2 = AgentSession(user_id=user_a.id, agent_type="data_agent", status="active")
    sa3 = AgentSession(user_id=user_a.id, agent_type="dashboard_agent", status="active")
    test_db.add_all([sa1, sa2, sa3])

    # User B: 2 agents
    sb1 = AgentSession(user_id=user_b.id, agent_type="orchestrator", status="active")
    sb2 = AgentSession(user_id=user_b.id, agent_type="data_agent", status="active")
    test_db.add_all([sb1, sb2])
    test_db.commit()

    registry.register_session(user_a.id, sa1.id, "orchestrator")
    registry.register_session(user_a.id, sa2.id, "data_agent")
    registry.register_session(user_a.id, sa3.id, "dashboard_agent")
    registry.register_session(user_b.id, sb1.id, "orchestrator")
    registry.register_session(user_b.id, sb2.id, "data_agent")

    return {
        "user_a": user_a, "user_b": user_b,
        "sa1": sa1, "sa2": sa2, "sa3": sa3,
        "sb1": sb1, "sb2": sb2,
    }


def test_sessions_list_isolated_per_user(setup, mock_redis):
    """sessions_list for user_a shows zero of user_b's sessions."""
    discovery = AgentDiscovery(redis_client=mock_redis)
    a_sessions = discovery.list_sessions(setup["user_a"].id)
    b_sessions = discovery.list_sessions(setup["user_b"].id)
    assert len(a_sessions) == 3
    assert len(b_sessions) == 2


def test_user_a_cannot_message_user_b_agent(setup, mock_redis, test_db):
    """User A's orchestrator cannot send to User B's data_agent."""
    bus = AgentMessageBus(db_session=test_db, redis_client=mock_redis)
    with pytest.raises(PermissionError):
        bus.send(
            setup["user_a"].id,
            setup["sa1"].id,
            setup["sb2"].id,
            {"text": "hello"},
            "request",
        )


def test_user_b_cannot_see_user_a_sessions(setup, mock_redis):
    """User B's discovery shows only their own sessions."""
    discovery = AgentDiscovery(redis_client=mock_redis)
    sessions = discovery.list_sessions(setup["user_b"].id)
    agent_types = {s["agent_type"] for s in sessions}
    assert "dashboard_agent" not in agent_types  # only user_a has this


def test_user_a_cannot_deregister_user_b_session(setup, mock_redis):
    """User A cannot deregister User B's session."""
    registry = AgentRegistry(redis_client=mock_redis)
    with pytest.raises(PermissionError):
        registry.deregister_session(setup["user_a"].id, setup["sb1"].id)


def test_drain_inbox_validates_ownership(setup, mock_redis, test_db):
    """drain_inbox rejects access to other user's session inbox."""
    bus = AgentMessageBus(db_session=test_db, redis_client=mock_redis)
    with pytest.raises(PermissionError):
        bus.drain_inbox(setup["user_a"].id, setup["sb2"].id)


def test_broadcast_user_scoped(setup, mock_redis, test_db):
    """broadcast only sends to the broadcasting user's agents."""
    bus = AgentMessageBus(db_session=test_db, redis_client=mock_redis)
    msg_ids = bus.broadcast(
        setup["user_a"].id, setup["sa1"].id, {"text": "broadcast"}
    )
    # Should send to sa2 and sa3, but not sb1/sb2
    assert len(msg_ids) == 2
    assert mock_redis.llen(f"agent:inbox:{setup['sb1'].id}") == 0
    assert mock_redis.llen(f"agent:inbox:{setup['sb2'].id}") == 0
