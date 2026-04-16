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
async def test_pending_datasets_are_added(ws_db, stub_user):
    """Pending ephemeral datasets inject immediately after upload; profiling
    status is no longer gated (see commit d2ad352)."""
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

    assert len(agent_ctx.available_connections) == 1


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


@pytest.mark.asyncio
async def test_inject_adds_connection_metadata(ws_db, stub_user):
    """Ready ephemeral dataset should also appear in connection_metadata."""
    from backend.api.websocket import _inject_conversation_datasets
    from backend.agents.context import AgentContext

    conn = DatabaseConnection(
        user_id="user-1", name="metrics", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="metrics.csv", is_ephemeral=True,
        profiling_status="ready",
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    ws_db.add(conn)
    ws_db.commit()

    agent_ctx = AgentContext(user_id="user-1", available_connections=[])

    await _inject_conversation_datasets(ws_db, stub_user, "thread-1", agent_ctx, [], None)

    assert conn.id in agent_ctx.available_connections
    assert any(m.id == conn.id for m in agent_ctx.connection_metadata)


@pytest.mark.asyncio
async def test_resolve_attachments_handles_connection_prefix(ws_db, stub_user):
    """connection:XX file IDs should resolve to a dataset file_contents entry."""
    from unittest.mock import patch, MagicMock
    from backend.api.websocket import _resolve_attachments

    conn = DatabaseConnection(
        user_id="user-1", name="sales", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="sales.csv", is_ephemeral=True,
        profiling_status="pending",
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    ws_db.add(conn)
    ws_db.commit()

    mock_chat_file_service = MagicMock()
    mock_chat_file_service.get_file.return_value = None

    file_contents, attachments = await _resolve_attachments(
        [f"connection:{conn.id}"], mock_chat_file_service, db=ws_db, user=stub_user,
    )

    assert len(file_contents) == 1
    assert file_contents[0]["file_id"] == f"connection:{conn.id}"
    assert file_contents[0]["original_name"] == "sales.csv"
    assert file_contents[0]["content_type"] == "text"
    assert file_contents[0]["profile_status"] == "processing"
    # Redis should NOT have been queried for connection: IDs
    mock_chat_file_service.get_file.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_attachments_invalid_connection_id(ws_db, stub_user):
    """Malformed or non-existent connection IDs are silently skipped."""
    from unittest.mock import MagicMock
    from backend.api.websocket import _resolve_attachments

    mock_svc = MagicMock()
    mock_svc.get_file.return_value = None

    file_contents, _ = await _resolve_attachments(
        ["connection:99999", "connection:abc"], mock_svc, db=ws_db, user=stub_user,
    )
    assert file_contents == []


@pytest.mark.asyncio
async def test_resolve_attachments_mixed_file_ids(ws_db, stub_user):
    """Mix of Redis file IDs and connection IDs should both resolve."""
    from unittest.mock import MagicMock
    from backend.api.websocket import _resolve_attachments

    conn = DatabaseConnection(
        user_id="user-1", name="orders", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="orders.csv", is_ephemeral=True,
        profiling_status="pending",
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    ws_db.add(conn)
    ws_db.commit()

    redis_file = {
        "file_id": "uuid-abc",
        "original_name": "photo.png",
        "mime_type": "image/png",
        "size": 1024,
        "content_type": "image",
        "base64_data": "data:image/png;base64,abc",
    }
    mock_svc = MagicMock()
    mock_svc.get_file.return_value = redis_file

    file_contents, _ = await _resolve_attachments(
        ["uuid-abc", f"connection:{conn.id}"], mock_svc, db=ws_db, user=stub_user,
    )

    assert len(file_contents) == 2
    file_ids = {fc["file_id"] for fc in file_contents}
    assert "uuid-abc" in file_ids
    assert f"connection:{conn.id}" in file_ids
