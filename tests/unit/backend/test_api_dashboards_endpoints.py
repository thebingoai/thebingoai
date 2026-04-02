"""Tests for dashboard API endpoints — CRUD via endpoint function calls.

Complements test_dashboards.py (which tests helpers and basic CRUD) by focusing
on endpoint-level behavior: user isolation across all operations, edge cases,
and response shape validation.
"""

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401 — resolve relationship mappers

from backend.api.dashboards import (
    DashboardCreate,
    DashboardUpdate,
    create_dashboard,
    delete_dashboard,
    get_dashboard,
    list_dashboards,
    update_dashboard,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory SQLite with Dashboard, User, DashboardRefreshRun tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        Dashboard.__table__,
        DashboardRefreshRun.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user_a(db):
    user = User(id="user-a", email="alice@example.com", auth_provider="sso")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def user_b(db):
    user = User(id="user-b", email="bob@example.com", auth_provider="sso")
    db.add(user)
    db.commit()
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dashboard(db, user_id, **overrides):
    """Insert a Dashboard row and return the ORM object."""
    now = datetime.utcnow()
    defaults = dict(
        user_id=user_id,
        title="Test Dashboard",
        description=None,
        widgets=[],
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    d = Dashboard(**defaults)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


# ---------------------------------------------------------------------------
# TestCreateDashboardEndpoint
# ---------------------------------------------------------------------------

class TestCreateDashboardEndpoint:
    """POST /api/dashboards — create a dashboard."""

    @pytest.mark.asyncio
    async def test_create_returns_201_fields(self, db, user_a):
        """Created dashboard response has all expected fields."""
        payload = DashboardCreate(title="Sales", description="Revenue KPIs", widgets=[{"type": "kpi"}])
        result = await create_dashboard(payload=payload, db=db, current_user=user_a)

        assert result.title == "Sales"
        assert result.description == "Revenue KPIs"
        assert result.widgets == [{"type": "kpi"}]
        assert isinstance(result.id, int)
        assert result.created_at is not None
        assert result.updated_at is not None

    @pytest.mark.asyncio
    async def test_create_assigns_user_id(self, db, user_a, user_b):
        """Dashboard is owned by the creating user."""
        payload = DashboardCreate(title="Alice's Dashboard")
        result = await create_dashboard(payload=payload, db=db, current_user=user_a)

        row = db.query(Dashboard).get(result.id)
        assert row.user_id == user_a.id

    @pytest.mark.asyncio
    async def test_create_default_empty_widgets(self, db, user_a):
        """Omitting widgets defaults to empty list."""
        payload = DashboardCreate(title="Bare")
        result = await create_dashboard(payload=payload, db=db, current_user=user_a)

        assert result.widgets == []


# ---------------------------------------------------------------------------
# TestListDashboardsEndpoint
# ---------------------------------------------------------------------------

class TestListDashboardsEndpoint:
    """GET /api/dashboards — list dashboards."""

    @pytest.mark.asyncio
    async def test_list_returns_only_own_dashboards(self, db, user_a, user_b):
        """Each user sees only their own dashboards."""
        _make_dashboard(db, user_a.id, title="A1")
        _make_dashboard(db, user_a.id, title="A2")
        _make_dashboard(db, user_b.id, title="B1")

        results_a = await list_dashboards(db=db, current_user=user_a)
        results_b = await list_dashboards(db=db, current_user=user_b)

        assert len(results_a) == 2
        assert {r.title for r in results_a} == {"A1", "A2"}
        assert len(results_b) == 1
        assert results_b[0].title == "B1"

    @pytest.mark.asyncio
    async def test_list_empty(self, db, user_a):
        """No dashboards -> empty list."""
        results = await list_dashboards(db=db, current_user=user_a)
        assert results == []


# ---------------------------------------------------------------------------
# TestGetDashboardEndpoint
# ---------------------------------------------------------------------------

class TestGetDashboardEndpoint:
    """GET /api/dashboards/{id} — get a specific dashboard."""

    @pytest.mark.asyncio
    async def test_get_own_dashboard(self, db, user_a):
        """User can retrieve their own dashboard."""
        d = _make_dashboard(db, user_a.id, title="My Board")
        result = await get_dashboard(dashboard_id=d.id, db=db, current_user=user_a)
        assert result.title == "My Board"

    @pytest.mark.asyncio
    async def test_get_other_users_dashboard_returns_404(self, db, user_a, user_b):
        """User cannot retrieve another user's dashboard."""
        d = _make_dashboard(db, user_b.id, title="Not Yours")
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard(dashboard_id=d.id, db=db, current_user=user_a)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, db, user_a):
        """Non-existent ID -> 404."""
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard(dashboard_id=99999, db=db, current_user=user_a)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestUpdateDashboardEndpoint
# ---------------------------------------------------------------------------

class TestUpdateDashboardEndpoint:
    """PUT /api/dashboards/{id} — partial update."""

    @pytest.mark.asyncio
    async def test_partial_update_title(self, db, user_a):
        """Updating only title preserves other fields."""
        d = _make_dashboard(db, user_a.id, title="Old", description="Keep", widgets=[{"v": 1}])
        payload = DashboardUpdate(title="New")
        result = await update_dashboard(dashboard_id=d.id, payload=payload, db=db, current_user=user_a)

        assert result.title == "New"
        assert result.description == "Keep"
        assert result.widgets == [{"v": 1}]

    @pytest.mark.asyncio
    async def test_update_other_users_dashboard_returns_404(self, db, user_a, user_b):
        """Cannot update another user's dashboard."""
        d = _make_dashboard(db, user_b.id, title="Bob's")
        payload = DashboardUpdate(title="Hijack")
        with pytest.raises(HTTPException) as exc_info:
            await update_dashboard(dashboard_id=d.id, payload=payload, db=db, current_user=user_a)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, db, user_a):
        """Non-existent ID -> 404."""
        payload = DashboardUpdate(title="Ghost")
        with pytest.raises(HTTPException) as exc_info:
            await update_dashboard(dashboard_id=99999, payload=payload, db=db, current_user=user_a)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestDeleteDashboardEndpoint
# ---------------------------------------------------------------------------

class TestDeleteDashboardEndpoint:
    """DELETE /api/dashboards/{id} — hard delete."""

    @pytest.mark.asyncio
    async def test_delete_removes_dashboard(self, db, user_a):
        """Deleted dashboard is removed from DB."""
        d = _make_dashboard(db, user_a.id, title="Delete Me")
        did = d.id
        await delete_dashboard(dashboard_id=did, db=db, current_user=user_a)

        assert db.query(Dashboard).filter(Dashboard.id == did).first() is None

    @pytest.mark.asyncio
    async def test_delete_other_users_dashboard_returns_404(self, db, user_a, user_b):
        """Cannot delete another user's dashboard."""
        d = _make_dashboard(db, user_b.id, title="Protected")
        with pytest.raises(HTTPException) as exc_info:
            await delete_dashboard(dashboard_id=d.id, db=db, current_user=user_a)
        assert exc_info.value.status_code == 404
        # Dashboard still exists
        assert db.query(Dashboard).filter(Dashboard.id == d.id).first() is not None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, db, user_a):
        """Non-existent ID -> 404."""
        with pytest.raises(HTTPException) as exc_info:
            await delete_dashboard(dashboard_id=99999, db=db, current_user=user_a)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_returns_none(self, db, user_a):
        """delete_dashboard returns None (maps to 204 No Content)."""
        d = _make_dashboard(db, user_a.id, title="Return None")
        result = await delete_dashboard(dashboard_id=d.id, db=db, current_user=user_a)
        assert result is None
