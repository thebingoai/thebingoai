"""Tests for connection API endpoints — list, create, delete via endpoint function calls.

Connections involve encryption, schema discovery, and profiling. These tests mock
out external dependencies and focus on the endpoint-level logic: ownership,
persistence, and error handling.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.database_connection import DatabaseConnection, DatabaseType
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.team_connection_policy import TeamConnectionPolicy
import backend.models.user_skill  # noqa: F401 — resolve relationship mappers

from backend.api.connections import (
    list_connections,
    create_connection,
    get_connection,
    delete_connection,
)
from backend.schemas.connection import ConnectionCreate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn_db():
    """In-memory SQLite with Connection, User, Dashboard tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        DatabaseConnection.__table__,
        Dashboard.__table__,
        DashboardRefreshRun.__table__,
        TeamConnectionPolicy.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user_a(conn_db):
    user = User(id="user-a", email="alice@example.com", auth_provider="sso")
    conn_db.add(user)
    conn_db.commit()
    return user


@pytest.fixture
def user_b(conn_db):
    user = User(id="user-b", email="bob@example.com", auth_provider="sso")
    conn_db.add(user)
    conn_db.commit()
    return user


def _insert_connection(db, user_id, **overrides):
    """Insert a DatabaseConnection row with mock-encrypted password."""
    defaults = dict(
        user_id=user_id,
        name="Test DB",
        db_type="postgres",
        host="localhost",
        port=5432,
        database="testdb",
        username="admin",
    )
    defaults.update(overrides)
    conn = DatabaseConnection(**defaults)
    conn.password = "secret"
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


# ---------------------------------------------------------------------------
# TestListConnections
# ---------------------------------------------------------------------------

class TestListConnections:
    """GET /api/connections — list connections."""

    @pytest.mark.asyncio
    async def test_list_returns_only_own_connections(self, conn_db, user_a, user_b):
        """Each user sees only their own connections."""
        _insert_connection(conn_db, user_a.id, name="Alice-DB")
        _insert_connection(conn_db, user_b.id, name="Bob-DB")

        result_a = await list_connections(current_user=user_a, db=conn_db)
        result_b = await list_connections(current_user=user_b, db=conn_db)

        assert len(result_a) == 1
        assert result_a[0].name == "Alice-DB"
        assert len(result_b) == 1
        assert result_b[0].name == "Bob-DB"

    @pytest.mark.asyncio
    async def test_list_empty(self, conn_db, user_a):
        """No connections -> empty list."""
        result = await list_connections(current_user=user_a, db=conn_db)
        assert result == []


# ---------------------------------------------------------------------------
# TestGetConnection
# ---------------------------------------------------------------------------

class TestGetConnection:
    """GET /api/connections/{id} — get a specific connection."""

    @pytest.mark.asyncio
    async def test_get_own_connection(self, conn_db, user_a):
        """User can retrieve their own connection."""
        conn = _insert_connection(conn_db, user_a.id, name="My DB")
        result = await get_connection(connection_id=conn.id, current_user=user_a, db=conn_db)
        assert result.name == "My DB"

    @pytest.mark.asyncio
    async def test_get_other_users_connection_returns_404(self, conn_db, user_a, user_b):
        """User cannot retrieve another user's connection."""
        conn = _insert_connection(conn_db, user_b.id, name="Not Yours")
        with pytest.raises(HTTPException) as exc_info:
            await get_connection(connection_id=conn.id, current_user=user_a, db=conn_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, conn_db, user_a):
        """Non-existent ID -> 404."""
        with pytest.raises(HTTPException) as exc_info:
            await get_connection(connection_id=99999, current_user=user_a, db=conn_db)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestCreateConnection
# ---------------------------------------------------------------------------

class TestCreateConnection:
    """POST /api/connections — create a connection."""

    def _make_request(self, **overrides):
        """Build a ConnectionCreate with valid defaults."""
        # Ensure 'postgres' is registered
        DatabaseType.register("postgres", "PostgreSQL")
        defaults = dict(
            name="New DB",
            db_type="postgres",
            host="db.example.com",
            port=5432,
            database="mydb",
            username="admin",
            password="s3cret",
        )
        defaults.update(overrides)
        return ConnectionCreate(**defaults)

    @pytest.mark.asyncio
    async def test_create_persists_connection(self, conn_db, user_a):
        """Created connection is persisted in the database."""
        request = self._make_request(name="Created DB")

        # Mock schema discovery + profiling to avoid real DB connections
        mock_connector = MagicMock()
        mock_connector.__enter__ = MagicMock(return_value=mock_connector)
        mock_connector.__exit__ = MagicMock(return_value=False)

        mock_profile_task = MagicMock()
        mock_profile_task.delay = MagicMock()

        with patch("backend.api.connections.get_connector", return_value=mock_connector), \
             patch("backend.api.connections.discover_schema", return_value={"table_names": ["t1"]}), \
             patch("backend.api.connections.generate_schema_json", return_value={}), \
             patch("backend.api.connections.save_schema_file", return_value="/tmp/schema.json"), \
             patch("backend.api.connections.settings") as mock_settings, \
             patch("backend.tasks.profiling_tasks.profile_connection", mock_profile_task):
            mock_settings.enable_governance = False

            result = await create_connection(request=request, current_user=user_a, db=conn_db)

        assert result.name == "Created DB"
        assert result.user_id == user_a.id
        assert result.db_type == "postgres"

        # Verify persisted
        row = conn_db.query(DatabaseConnection).filter(DatabaseConnection.name == "Created DB").first()
        assert row is not None
        assert row.user_id == user_a.id

    @pytest.mark.asyncio
    async def test_create_survives_schema_discovery_failure(self, conn_db, user_a):
        """Connection is still created even if schema discovery raises."""
        request = self._make_request(name="No Schema")

        with patch("backend.api.connections.get_connector", side_effect=Exception("Connection refused")), \
             patch("backend.api.connections.settings") as mock_settings:
            mock_settings.enable_governance = False

            result = await create_connection(request=request, current_user=user_a, db=conn_db)

        assert result.name == "No Schema"
        row = conn_db.query(DatabaseConnection).filter(DatabaseConnection.name == "No Schema").first()
        assert row is not None


# ---------------------------------------------------------------------------
# TestDeleteConnection
# ---------------------------------------------------------------------------

class TestDeleteConnection:
    """DELETE /api/connections/{id} — delete a connection."""

    @pytest.mark.asyncio
    async def test_delete_removes_connection(self, conn_db, user_a):
        """Deleted connection is removed from DB."""
        conn = _insert_connection(conn_db, user_a.id, name="Delete Me")
        cid = conn.id

        with patch("backend.api.connections.get_connector_registration", return_value=None), \
             patch("backend.api.connections.delete_schema_file"), \
             patch("backend.services.connection_context.delete_context_file"):
            await delete_connection(connection_id=cid, current_user=user_a, db=conn_db)

        assert conn_db.query(DatabaseConnection).filter(DatabaseConnection.id == cid).first() is None

    @pytest.mark.asyncio
    async def test_delete_other_users_connection_returns_404(self, conn_db, user_a, user_b):
        """Cannot delete another user's connection."""
        conn = _insert_connection(conn_db, user_b.id, name="Protected")

        with pytest.raises(HTTPException) as exc_info:
            with patch("backend.api.connections.get_connector_registration", return_value=None), \
                 patch("backend.api.connections.delete_schema_file"), \
                 patch("backend.services.connection_context.delete_context_file"):
                await delete_connection(connection_id=conn.id, current_user=user_a, db=conn_db)

        assert exc_info.value.status_code == 404
        # Connection still exists
        assert conn_db.query(DatabaseConnection).filter(DatabaseConnection.id == conn.id).first() is not None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, conn_db, user_a):
        """Non-existent ID -> 404."""
        with pytest.raises(HTTPException) as exc_info:
            with patch("backend.api.connections.get_connector_registration", return_value=None), \
                 patch("backend.api.connections.delete_schema_file"), \
                 patch("backend.services.connection_context.delete_context_file"):
                await delete_connection(connection_id=99999, current_user=user_a, db=conn_db)

        assert exc_info.value.status_code == 404
