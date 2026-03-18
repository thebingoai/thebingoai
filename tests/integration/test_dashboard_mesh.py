"""Integration tests for dashboard creation via agent mesh."""

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


@pytest.fixture
def test_user(test_db):
    user = User(email="mesh-test@example.com", hashed_password="hashed")
    test_db.add(user)
    test_db.commit()
    return user, test_db


@pytest.mark.integration
def test_session_auto_provisioning(test_user, mock_redis):
    """
    When mesh is enabled, auto-provisioning creates sessions for
    orchestrator, data_agent, dashboard_agent, rag_agent.
    """
    user, db = test_user
    registry = AgentRegistry(redis_client=mock_redis)
    discovery = AgentDiscovery(redis_client=mock_redis)

    # Simulate auto-provisioning
    built_in_types = ["orchestrator", "data_agent", "dashboard_agent", "rag_agent"]
    import uuid

    for agent_type in built_in_types:
        session_id = str(uuid.uuid4())
        registry.register_session(user.id, session_id, agent_type)

    sessions = discovery.list_sessions(user.id)
    assert len(sessions) == 4
    types = {s["agent_type"] for s in sessions}
    assert types == {"orchestrator", "data_agent", "dashboard_agent", "rag_agent"}


@pytest.mark.integration
def test_inter_agent_message_flow(test_user, mock_redis):
    """
    Dashboard agent can send messages to data agent and receive responses
    within the same user's mesh.
    """
    user, db = test_user
    registry = AgentRegistry(redis_client=mock_redis)

    # Create sessions
    registry.register_session(user.id, "dash-session", "dashboard_agent")
    registry.register_session(user.id, "data-session", "data_agent")

    bus = AgentMessageBus(db_session=db, redis_client=mock_redis)

    # Dashboard agent asks data agent
    msg_id = bus.send(
        user.id, "dash-session", "data-session",
        {"text": "list tables for connection 5"},
        "request",
    )
    assert msg_id is not None

    # Data agent drains its inbox
    inbox = bus.drain_inbox(user.id, "data-session")
    assert len(inbox) == 1
    assert inbox[0]["content"]["text"] == "list tables for connection 5"

    # Data agent responds
    correlation_id = inbox[0].get("correlation_id")
    bus.respond(
        user.id, "data-session", "dash-session",
        {"tables": ["orders", "customers", "products"]},
        correlation_id,
    )

    # Dashboard agent drains its inbox
    response = bus.drain_inbox(user.id, "dash-session")
    assert len(response) == 1
    assert response[0]["content"]["tables"] == ["orders", "customers", "products"]


@pytest.mark.integration
def test_data_agent_schema_reuse_pattern(test_user, mock_redis):
    """
    Data agent session persists in Redis — multiple messages use the same session.
    """
    user, db = test_user
    registry = AgentRegistry(redis_client=mock_redis)

    registry.register_session(user.id, "data-session", "data_agent")

    # Verify session persists across heartbeats
    assert registry.heartbeat("data-session") is True

    data = registry.get_session("data-session")
    assert data["status"] == "active"
    assert data["agent_type"] == "data_agent"

    # Session ID remains the same
    discovery = AgentDiscovery(redis_client=mock_redis)
    found = discovery.find_session_by_type(user.id, "data_agent")
    assert found["session_id"] == "data-session"
