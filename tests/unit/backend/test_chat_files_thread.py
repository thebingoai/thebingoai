"""Tests for thread_id association in the chat file upload endpoint."""

import sys
import io
import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Stub heavy optional deps not installed in the local test env
for mod in ("PyPDF2", "PIL", "PIL.Image", "docx", "docx.api"):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import backend.models.user_skill  # noqa: F401
from backend.database.base import Base
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.conversation_service import ConversationService


@pytest.fixture
def chat_db():
    """In-memory SQLite with Conversation table."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        Conversation.__table__,
        Message.__table__,
    ])
    session = sessionmaker(bind=engine)()

    session.add(User(id="user-1", email="test@example.com", auth_provider="supabase"))
    session.add(User(id="user-2", email="other@example.com", auth_provider="supabase"))
    session.commit()
    yield session
    session.close()


@pytest.fixture
def stub_user():
    user = MagicMock()
    user.id = "user-1"
    user.email = "test@example.com"
    return user


def _mock_upload_file(filename="test.csv", content=b"a,b\n1,2\n3,4", mime="text/csv"):
    uf = AsyncMock()
    uf.filename = filename
    uf.content_type = mime
    uf.read = AsyncMock(return_value=content)
    return uf


def _mock_file_service():
    """Return patches for chat_file_service methods."""
    file_data = {
        "file_id": "file-123",
        "original_name": "test.csv",
        "mime_type": "text/csv",
        "size": 100,
        "content_type": "text",
        "profile_status": "processing",
    }
    return {
        "process_file": patch("backend.api.chat_files.chat_file_service.process_file", return_value=file_data.copy()),
        "store_file": patch("backend.api.chat_files.chat_file_service.store_file"),
        "save_raw_file": patch("backend.api.chat_files.chat_file_service.save_raw_file", return_value="s3/key"),
        "update_key": patch("backend.api.chat_files.chat_file_service.update_file_storage_key"),
        "profile_task": patch("backend.tasks.profiling_tasks.profile_chat_file"),
    }, file_data


@pytest.mark.asyncio
async def test_upload_without_thread_id_creates_conversation(chat_db, stub_user):
    from backend.api.chat_files import upload_chat_files

    patches, _ = _mock_file_service()
    mocks = {k: p.start() for k, p in patches.items()}
    try:
        result = await upload_chat_files(
            files=[_mock_upload_file()],
            thread_id=None,
            current_user=stub_user,
            db=chat_db,
        )
    finally:
        for p in patches.values():
            p.stop()

    assert "thread_id" in result
    assert result["thread_id"] is not None

    conv = chat_db.query(Conversation).filter_by(thread_id=result["thread_id"]).first()
    assert conv is not None
    assert conv.user_id == "user-1"


@pytest.mark.asyncio
async def test_upload_with_valid_thread_id(chat_db, stub_user):
    from backend.api.chat_files import upload_chat_files

    conv = ConversationService.create_conversation(chat_db, "user-1", title="Existing")
    tid = conv.thread_id

    patches, _ = _mock_file_service()
    for p in patches.values():
        p.start()
    try:
        result = await upload_chat_files(
            files=[_mock_upload_file()],
            thread_id=tid,
            current_user=stub_user,
            db=chat_db,
        )
    finally:
        for p in patches.values():
            p.stop()

    assert result["thread_id"] == tid


@pytest.mark.asyncio
async def test_upload_with_other_users_thread_returns_403(chat_db, stub_user):
    from backend.api.chat_files import upload_chat_files
    from fastapi import HTTPException

    conv = ConversationService.create_conversation(chat_db, "user-2", title="Other User")
    tid = conv.thread_id

    patches, _ = _mock_file_service()
    for p in patches.values():
        p.start()
    try:
        with pytest.raises(HTTPException) as exc_info:
            await upload_chat_files(
                files=[_mock_upload_file()],
                thread_id=tid,
                current_user=stub_user,
                db=chat_db,
            )
        assert exc_info.value.status_code == 403
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_response_includes_auto_processing_for_csv(chat_db, stub_user):
    from backend.api.chat_files import upload_chat_files

    patches, _ = _mock_file_service()
    for p in patches.values():
        p.start()
    try:
        result = await upload_chat_files(
            files=[_mock_upload_file()],
            thread_id=None,
            current_user=stub_user,
            db=chat_db,
        )
    finally:
        for p in patches.values():
            p.stop()

    file_result = result["files"][0]
    assert file_result["thread_id"] == result["thread_id"]
    assert file_result["auto_processing"] is True


@pytest.mark.asyncio
async def test_redis_file_data_contains_thread_id(chat_db, stub_user):
    from backend.api.chat_files import upload_chat_files

    patches, _ = _mock_file_service()
    mocks = {k: p.start() for k, p in patches.items()}
    try:
        result = await upload_chat_files(
            files=[_mock_upload_file()],
            thread_id=None,
            current_user=stub_user,
            db=chat_db,
        )
    finally:
        for p in patches.values():
            p.stop()

    # store_file is called with file_data dict that should have thread_id
    stored_data = mocks["store_file"].call_args[0][0]
    assert "thread_id" in stored_data
    assert stored_data["thread_id"] == result["thread_id"]
