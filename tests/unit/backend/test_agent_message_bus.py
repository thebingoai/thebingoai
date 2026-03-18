"""Tests for AgentMessageBus service."""

import pytest
import fakeredis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.base import Base
from backend.models.user import User
from backend.models.agent_session import AgentSession
from backend.models.agent_message import AgentMessage
from backend.services.agent_registry import AgentRegistry
from backend.services.agent_message_bus import AgentMessageBus

_TABLES = [User.__table__, AgentSession.__table__, AgentMessage.__table__]


@pytest.fixture
def mock_redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=_TABLES)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def test_user(test_db):
    user = User(email="bus-test@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user, test_db


@pytest.fixture
def second_user(test_db):
    user = User(email="other@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def sessions(test_user, mock_redis):
    """Create two sessions for test user and register them in Redis."""
    user, db = test_user
    s1 = AgentSession(user_id=user.id, agent_type="orchestrator", status="active")
    s2 = AgentSession(user_id=user.id, agent_type="data_agent", status="active")
    db.add_all([s1, s2])
    db.commit()

    registry = AgentRegistry(redis_client=mock_redis)
    registry.register_session(user.id, s1.id, "orchestrator")
    registry.register_session(user.id, s2.id, "data_agent")

    return s1, s2, user, db


def test_send_writes_to_postgres_and_redis(sessions, mock_redis):
    """send() writes message to both Postgres and Redis inbox."""
    s1, s2, user, db = sessions
    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)
    bus.send(user.id, s1.id, s2.id, {"text": "hello"}, "request")

    # Postgres
    msgs = db.query(AgentMessage).filter_by(user_id=user.id).all()
    assert len(msgs) == 1
    assert msgs[0].content == {"text": "hello"}
    assert msgs[0].message_type == "request"

    # Redis inbox
    assert mock_redis.llen(f"agent:inbox:{s2.id}") == 1


def test_send_cross_user_rejected(test_user, second_user, mock_redis):
    """send() rejects messaging sessions owned by different users."""
    user, db = test_user
    s1 = AgentSession(user_id=user.id, agent_type="orchestrator", status="active")
    s2 = AgentSession(user_id=second_user.id, agent_type="data_agent", status="active")
    db.add_all([s1, s2])
    db.commit()

    registry = AgentRegistry(redis_client=mock_redis)
    registry.register_session(user.id, s1.id, "orchestrator")
    registry.register_session(second_user.id, s2.id, "data_agent")

    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)
    with pytest.raises(PermissionError):
        bus.send(user.id, s1.id, s2.id, {"text": "hello"}, "request")


def test_drain_inbox(sessions, mock_redis):
    """drain_inbox returns all pending messages and empties the list."""
    s1, s2, user, db = sessions
    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)

    # Send 3 messages
    for i in range(3):
        bus.send(user.id, s1.id, s2.id, {"text": f"msg {i}"}, "request")

    messages = bus.drain_inbox(user.id, s2.id)
    assert len(messages) == 3
    assert mock_redis.llen(f"agent:inbox:{s2.id}") == 0


def test_drain_inbox_wrong_user(sessions, mock_redis):
    """drain_inbox rejects wrong user."""
    s1, s2, user, db = sessions
    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)
    with pytest.raises(PermissionError):
        bus.drain_inbox("wrong_user", s2.id)


def test_broadcast(sessions, mock_redis):
    """broadcast sends to all user's agents except sender."""
    s1, s2, user, db = sessions

    # Add a third session
    s3 = AgentSession(user_id=user.id, agent_type="rag_agent", status="active")
    db.add(s3)
    db.commit()
    registry = AgentRegistry(redis_client=mock_redis)
    registry.register_session(user.id, s3.id, "rag_agent")

    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)
    msg_ids = bus.broadcast(user.id, s1.id, {"text": "broadcast msg"})

    assert len(msg_ids) == 2
    assert mock_redis.llen(f"agent:inbox:{s2.id}") == 1
    assert mock_redis.llen(f"agent:inbox:{s3.id}") == 1
    assert mock_redis.llen(f"agent:inbox:{s1.id}") == 0  # sender excluded


def test_get_history(sessions, mock_redis):
    """get_history returns messages from Postgres."""
    s1, s2, user, db = sessions
    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)

    bus.send(user.id, s1.id, s2.id, {"text": "msg 1"}, "request")
    bus.send(user.id, s2.id, s1.id, {"text": "reply 1"}, "response")

    history = bus.get_history(user.id, s1.id, limit=20)
    assert len(history) == 2


def test_respond_publishes_to_correlation_channel(sessions, mock_redis):
    """respond() sends message and publishes on correlation channel."""
    s1, s2, user, db = sessions
    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)
    msg_id = bus.respond(user.id, s2.id, s1.id, {"text": "response"}, "corr-123")
    assert msg_id is not None

    # Should have written to Postgres
    msgs = db.query(AgentMessage).filter_by(correlation_id="corr-123").all()
    assert len(msgs) == 1
    assert msgs[0].message_type == "response"
