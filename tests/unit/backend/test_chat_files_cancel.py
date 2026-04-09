"""Tests for cancel dataset and conversation datasets endpoints."""

import sys
import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

for _mod in ("PyPDF2", "PIL", "PIL.Image", "docx", "docx.api"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import backend.models.user_skill  # noqa: F401
from backend.database.base import Base
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.services.conversation_service import ConversationService


@pytest.fixture
def cancel_db():
    """In-memory SQLite with Conversation + DatabaseConnection tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        Conversation.__table__,
        Message.__table__,
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


# ---- Cancel endpoint tests ----

@pytest.mark.asyncio
async def test_cancel_deletes_connection_and_cleans_redis(cancel_db, stub_user):
    from backend.api.chat_files import cancel_dataset

    # Create a connection
    conn = DatabaseConnection(
        user_id="user-1", name="test", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="test.csv", is_ephemeral=True,
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    cancel_db.add(conn)
    cancel_db.commit()

    file_data = {
        "file_id": "file-1",
        "original_name": "test.csv",
        "thread_id": "thread-1",
        "profile_status": "processing",
    }

    with patch("backend.api.chat_files.chat_file_service.get_file", return_value=file_data), \
         patch("backend.api.chat_files.chat_file_service.delete_file") as mock_delete, \
         patch("backend.services.ws_connection_manager.ConnectionManager.publish_to_user_sync") as mock_ws:

        result = await cancel_dataset(
            file_id="file-1",
            current_user=stub_user,
            db=cancel_db,
        )

    assert result["status"] == "cancelled"
    mock_delete.assert_called_once_with("file-1")
    mock_ws.assert_called_once()
    ws_msg = mock_ws.call_args[0][1]
    assert ws_msg["step"] == "cancelled"

    # Connection should be deleted
    assert cancel_db.query(DatabaseConnection).filter_by(source_filename="test.csv").first() is None


@pytest.mark.asyncio
async def test_cancel_returns_404_for_unknown_file(cancel_db, stub_user):
    from backend.api.chat_files import cancel_dataset
    from fastapi import HTTPException

    with patch("backend.api.chat_files.chat_file_service.get_file", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await cancel_dataset(file_id="nonexistent", current_user=stub_user, db=cancel_db)
        assert exc_info.value.status_code == 404


# ---- Conversation datasets endpoint tests ----

@pytest.mark.asyncio
async def test_conversation_datasets_returns_list(cancel_db, stub_user):
    from backend.api.chat_files import get_conversation_datasets

    conv = ConversationService.create_conversation(cancel_db, "user-1", title="Test")

    # Create a connection for a dataset
    conn = DatabaseConnection(
        user_id="user-1", name="data", db_type="dataset",
        host="internal", port=0, database="dataset", username="dataset",
        source_filename="data.csv", is_ephemeral=True,
        profiling_status="ready",
    )
    conn.password = "dataset"
    conn.ssl_ca_cert = None
    cancel_db.add(conn)
    cancel_db.commit()

    # Mock Redis scan to return matching file data
    file_data = json.dumps({
        "file_id": "file-1",
        "original_name": "data.csv",
        "thread_id": conv.thread_id,
        "profile_status": "processing",
    })

    mock_redis = MagicMock()
    mock_redis.scan.return_value = (0, ["chat_file:file-1"])
    mock_redis.get.return_value = file_data
    mock_redis.close = MagicMock()

    with patch("backend.api.chat_files.settings") as mock_settings, \
         patch("redis.from_url", return_value=mock_redis):
        mock_settings.redis_url = "redis://localhost"
        result = await get_conversation_datasets(
            thread_id=conv.thread_id,
            current_user=stub_user,
            db=cancel_db,
        )

    assert len(result["datasets"]) == 1
    ds = result["datasets"][0]
    assert ds["file_id"] == "file-1"
    assert ds["name"] == "data.csv"
    assert ds["status"] == "ready"
    assert ds["connection_id"] == conn.id


@pytest.mark.asyncio
async def test_conversation_datasets_empty_for_no_datasets(cancel_db, stub_user):
    from backend.api.chat_files import get_conversation_datasets

    conv = ConversationService.create_conversation(cancel_db, "user-1", title="Empty")

    mock_redis = MagicMock()
    mock_redis.scan.return_value = (0, [])
    mock_redis.close = MagicMock()

    with patch("backend.api.chat_files.settings") as mock_settings, \
         patch("redis.from_url", return_value=mock_redis):
        mock_settings.redis_url = "redis://localhost"
        result = await get_conversation_datasets(
            thread_id=conv.thread_id,
            current_user=stub_user,
            db=cancel_db,
        )

    assert result["datasets"] == []


@pytest.mark.asyncio
async def test_conversation_datasets_returns_403_for_other_user(cancel_db, stub_user):
    from backend.api.chat_files import get_conversation_datasets
    from fastapi import HTTPException

    # Create conversation for another user
    cancel_db.add(User(id="user-2", email="other@example.com", auth_provider="supabase"))
    cancel_db.commit()
    conv = ConversationService.create_conversation(cancel_db, "user-2", title="Other")

    with pytest.raises(HTTPException) as exc_info:
        await get_conversation_datasets(
            thread_id=conv.thread_id,
            current_user=stub_user,
            db=cancel_db,
        )
    assert exc_info.value.status_code == 403
