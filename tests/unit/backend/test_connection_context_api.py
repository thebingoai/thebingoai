"""Unit tests for connection context API endpoints: get_profiling_status, reprofile_connection, get_connection_context."""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from fastapi import HTTPException

from backend.api.connections import get_profiling_status, reprofile_connection, get_connection_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(user_id="user-1"):
    user = MagicMock()
    user.id = user_id
    return user


def _mock_connection(**overrides):
    defaults = dict(
        id=1,
        user_id="user-1",
        name="Test DB",
        profiling_status="pending",
        profiling_progress=None,
        profiling_error=None,
        profiling_started_at=None,
        profiling_completed_at=None,
        schema_json_path="/path/schema.json",
    )
    defaults.update(overrides)
    conn = MagicMock()
    for k, v in defaults.items():
        setattr(conn, k, v)
    return conn


def _mock_db(first_return=None):
    """Return a MagicMock db session whose .query().filter().first() chain returns *first_return*."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = first_return
    return db


# ---------------------------------------------------------------------------
# TestGetProfilingStatus
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetProfilingStatus:

    async def test_returns_status_fields(self):
        started = datetime(2026, 3, 30, 10, 0, 0)
        conn = _mock_connection(
            profiling_status="in_progress",
            profiling_progress="3/5 tables",
            profiling_error=None,
            profiling_started_at=started,
            profiling_completed_at=None,
        )
        db = _mock_db(conn)
        user = _mock_user()

        result = await get_profiling_status(connection_id=1, current_user=user, db=db)

        assert result["status"] == "in_progress"
        assert result["progress"] == "3/5 tables"
        assert result["error"] is None
        assert result["started_at"] == started.isoformat()
        assert result["completed_at"] is None

    async def test_connection_not_found_404(self):
        db = _mock_db(None)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await get_profiling_status(connection_id=999, current_user=user, db=db)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestReprofileConnection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestReprofileConnection:

    @patch("backend.tasks.profiling_tasks.profile_connection")
    async def test_queues_profiling_task(self, mock_task):
        mock_task.delay = MagicMock()
        conn = _mock_connection(profiling_status="ready")
        db = _mock_db(conn)
        user = _mock_user()

        await reprofile_connection(connection_id=1, current_user=user, db=db)

        mock_task.delay.assert_called_once_with(conn.id)

    @patch("backend.tasks.profiling_tasks.profile_connection")
    async def test_resets_status_to_pending(self, mock_task):
        mock_task.delay = MagicMock()
        conn = _mock_connection(profiling_status="ready")
        db = _mock_db(conn)
        user = _mock_user()

        await reprofile_connection(connection_id=1, current_user=user, db=db)

        assert conn.profiling_status == "pending"

    async def test_in_progress_returns_400(self):
        conn = _mock_connection(profiling_status="in_progress")
        db = _mock_db(conn)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await reprofile_connection(connection_id=1, current_user=user, db=db)
        assert exc_info.value.status_code == 400
        assert "already in progress" in exc_info.value.detail

    async def test_no_schema_returns_400(self):
        conn = _mock_connection(profiling_status="ready", schema_json_path=None)
        db = _mock_db(conn)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await reprofile_connection(connection_id=1, current_user=user, db=db)
        assert exc_info.value.status_code == 400
        assert "Schema" in exc_info.value.detail

    async def test_connection_not_found_404(self):
        db = _mock_db(None)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await reprofile_connection(connection_id=999, current_user=user, db=db)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestGetConnectionContext
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGetConnectionContext:

    @patch("backend.services.connection_context.load_context_file")
    async def test_returns_context_json_when_ready(self, mock_load):
        context_data = {"tables": ["orders"], "summary": "test context"}
        mock_load.return_value = context_data
        conn = _mock_connection(profiling_status="ready")
        db = _mock_db(conn)
        user = _mock_user()

        result = await get_connection_context(connection_id=1, current_user=user, db=db)

        assert result == context_data
        mock_load.assert_called_once_with(1)

    async def test_not_ready_returns_409(self):
        conn = _mock_connection(profiling_status="in_progress")
        db = _mock_db(conn)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await get_connection_context(connection_id=1, current_user=user, db=db)
        assert exc_info.value.status_code == 409
        assert "not ready" in exc_info.value.detail

    @patch("backend.services.connection_context.load_context_file", side_effect=FileNotFoundError("missing"))
    async def test_context_file_missing_returns_404(self, mock_load):
        conn = _mock_connection(profiling_status="ready")
        db = _mock_db(conn)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await get_connection_context(connection_id=1, current_user=user, db=db)
        assert exc_info.value.status_code == 404
        assert "Context file not found" in exc_info.value.detail

    async def test_connection_not_found_404(self):
        db = _mock_db(None)
        user = _mock_user()

        with pytest.raises(HTTPException) as exc_info:
            await get_connection_context(connection_id=999, current_user=user, db=db)
        assert exc_info.value.status_code == 404
