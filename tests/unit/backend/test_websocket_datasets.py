"""Tests for conversation dataset injection in the WebSocket handler."""

import sys
from unittest.mock import MagicMock

import pytest

for _mod in ("PyPDF2", "PIL", "PIL.Image", "docx", "docx.api"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.models.user_skill  # noqa: F401
from backend.database.base import Base
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection


@pytest.fixture
def ws_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        DatabaseConnection.__table__,
    ])
    session = sessionmaker(bind=engine)()
    session.add(User(id="user-1", email="test@example.com", auth_provider="supabase"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def stub_user():
    user = MagicMock()
    user.id = "user-1"
    return user


def _make_agent_context(connections=None):
    ctx = MagicMock()
    ctx.available_connections = connections or []
    return ctx


@pytest.mark.asyncio
async def test_ready_ephemeral_datasets_added_to_available_connections(ws_db, stub_user):
    from backend.api.websocket import _inject_conversation_datasets

    conn = DatabaseConnection(
        user_id="user-1", name="data", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="data.csv", is_ephemeral=True,
        profiling_status="ready",
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    ws_db.add(conn)
    ws_db.commit()

    agent_ctx = _make_agent_context()
    file_contents = []

    await _inject_conversation_datasets(
        ws_db, stub_user, "thread-1",
        agent_ctx, file_contents, None,
    )

    assert conn.id in agent_ctx.available_connections


@pytest.mark.asyncio
async def test_pending_datasets_not_added(ws_db, stub_user):
    from backend.api.websocket import _inject_conversation_datasets

    conn = DatabaseConnection(
        user_id="user-1", name="data2", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="data2.csv", is_ephemeral=True,
        profiling_status="pending",
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    ws_db.add(conn)
    ws_db.commit()

    agent_ctx = _make_agent_context()
    file_contents = []

    await _inject_conversation_datasets(
        ws_db, stub_user, "thread-1",
        agent_ctx, file_contents, None,
    )

    assert len(agent_ctx.available_connections) == 0


@pytest.mark.asyncio
async def test_no_ephemeral_datasets_passes_empty(ws_db, stub_user):
    from backend.api.websocket import _inject_conversation_datasets

    agent_ctx = _make_agent_context()
    file_contents = []

    await _inject_conversation_datasets(
        ws_db, stub_user, "thread-empty",
        agent_ctx, file_contents, None,
    )

    assert agent_ctx.available_connections == []
