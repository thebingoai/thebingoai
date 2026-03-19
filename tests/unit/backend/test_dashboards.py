"""Unit tests for backend.api.dashboards — CRUD operations on dashboards."""

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
    _dashboard_to_response,
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
def dashboard_db():
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
def test_user(dashboard_db):
    user = User(id="user-1", email="test@example.com", auth_provider="sso")
    dashboard_db.add(user)
    dashboard_db.commit()
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
# TestDashboardToResponse
# ---------------------------------------------------------------------------

class TestDashboardToResponse:
    """Tests for the _dashboard_to_response helper."""

    def test_full_fields(self, dashboard_db, test_user):
        """All schedule fields set — verify every field in the response."""
        now = datetime.utcnow()
        d = _make_dashboard(
            dashboard_db,
            test_user.id,
            title="Full",
            description="A description",
            widgets=[{"type": "kpi", "label": "Revenue"}],
            schedule_type="preset",
            schedule_value="1h",
            cron_expression="0 * * * *",
            schedule_active=True,
            next_run_at=now,
            last_run_at=now,
        )

        resp = _dashboard_to_response(d)

        assert resp.id == d.id
        assert resp.title == "Full"
        assert resp.description == "A description"
        assert resp.widgets == [{"type": "kpi", "label": "Revenue"}]
        assert resp.schedule_type == "preset"
        assert resp.schedule_value == "1h"
        assert resp.cron_expression == "0 * * * *"
        assert resp.schedule_active is True
        assert resp.next_run_at == str(now)
        assert resp.last_run_at == str(now)

    def test_none_schedule_fields(self, dashboard_db, test_user):
        """schedule_type / schedule_value / cron_expression all None."""
        d = _make_dashboard(dashboard_db, test_user.id, title="No Schedule")

        resp = _dashboard_to_response(d)

        assert resp.schedule_type is None
        assert resp.schedule_value is None
        assert resp.cron_expression is None

    def test_none_widgets_returns_empty_list(self, dashboard_db, test_user):
        """When widgets is None on the ORM object, response should be []."""
        d = _make_dashboard(dashboard_db, test_user.id, title="Null Widgets", widgets=None)

        resp = _dashboard_to_response(d)

        assert resp.widgets == []

    def test_schedule_active_none_returns_false(self, dashboard_db, test_user):
        """When schedule_active is None, response should default to False."""
        d = _make_dashboard(dashboard_db, test_user.id, title="Null Active")
        # Force None at the Python level to bypass column default
        d.schedule_active = None

        resp = _dashboard_to_response(d)

        assert resp.schedule_active is False

    def test_datetime_fields_converted_to_str(self, dashboard_db, test_user):
        """created_at / updated_at should appear as strings in the response."""
        d = _make_dashboard(dashboard_db, test_user.id, title="TS")

        resp = _dashboard_to_response(d)

        assert isinstance(resp.created_at, str)
        assert isinstance(resp.updated_at, str)
        assert str(d.created_at) == resp.created_at
        assert str(d.updated_at) == resp.updated_at


# ---------------------------------------------------------------------------
# TestListDashboards
# ---------------------------------------------------------------------------

class TestListDashboards:
    """Tests for list_dashboards endpoint."""

    @pytest.mark.asyncio
    async def test_returns_all_dashboards_for_user(self, dashboard_db, test_user):
        _make_dashboard(dashboard_db, test_user.id, title="D1")
        _make_dashboard(dashboard_db, test_user.id, title="D2")
        _make_dashboard(dashboard_db, test_user.id, title="D3")

        result = await list_dashboards(db=dashboard_db, current_user=test_user)

        assert len(result) == 3
        titles = {r.title for r in result}
        assert titles == {"D1", "D2", "D3"}

    @pytest.mark.asyncio
    async def test_empty_list_when_no_dashboards(self, dashboard_db, test_user):
        result = await list_dashboards(db=dashboard_db, current_user=test_user)

        assert result == []

    @pytest.mark.asyncio
    async def test_user_isolation(self, dashboard_db, test_user):
        """Each user should only see their own dashboards."""
        other_user = User(id="user-2", email="other@example.com", auth_provider="sso")
        dashboard_db.add(other_user)
        dashboard_db.commit()

        _make_dashboard(dashboard_db, test_user.id, title="Mine")
        _make_dashboard(dashboard_db, other_user.id, title="Theirs")

        mine = await list_dashboards(db=dashboard_db, current_user=test_user)
        theirs = await list_dashboards(db=dashboard_db, current_user=other_user)

        assert len(mine) == 1
        assert mine[0].title == "Mine"
        assert len(theirs) == 1
        assert theirs[0].title == "Theirs"


# ---------------------------------------------------------------------------
# TestGetDashboard
# ---------------------------------------------------------------------------

class TestGetDashboard:
    """Tests for get_dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_found(self, dashboard_db, test_user):
        d = _make_dashboard(dashboard_db, test_user.id, title="Found Me")

        result = await get_dashboard(dashboard_id=d.id, db=dashboard_db, current_user=test_user)

        assert result.id == d.id
        assert result.title == "Found Me"

    @pytest.mark.asyncio
    async def test_not_found_invalid_id(self, dashboard_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard(dashboard_id=99999, db=dashboard_db, current_user=test_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_user_returns_404(self, dashboard_db, test_user):
        other_user = User(id="user-other", email="other2@example.com", auth_provider="sso")
        dashboard_db.add(other_user)
        dashboard_db.commit()

        d = _make_dashboard(dashboard_db, other_user.id, title="Not Yours")

        with pytest.raises(HTTPException) as exc_info:
            await get_dashboard(dashboard_id=d.id, db=dashboard_db, current_user=test_user)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestCreateDashboard
# ---------------------------------------------------------------------------

class TestCreateDashboard:
    """Tests for create_dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_basic_create_title_only(self, dashboard_db, test_user):
        payload = DashboardCreate(title="New Dashboard")

        result = await create_dashboard(payload=payload, db=dashboard_db, current_user=test_user)

        assert result.title == "New Dashboard"
        assert result.description is None
        assert result.widgets == []

    @pytest.mark.asyncio
    async def test_create_with_widgets(self, dashboard_db, test_user):
        widgets = [{"type": "chart", "query": "SELECT 1"}, {"type": "kpi"}]
        payload = DashboardCreate(title="With Widgets", widgets=widgets)

        result = await create_dashboard(payload=payload, db=dashboard_db, current_user=test_user)

        assert result.widgets == widgets

    @pytest.mark.asyncio
    async def test_no_description_is_none(self, dashboard_db, test_user):
        payload = DashboardCreate(title="No Desc")

        result = await create_dashboard(payload=payload, db=dashboard_db, current_user=test_user)

        assert result.description is None

    @pytest.mark.asyncio
    async def test_assigns_correct_user_id(self, dashboard_db, test_user):
        payload = DashboardCreate(title="User Check")

        await create_dashboard(payload=payload, db=dashboard_db, current_user=test_user)

        row = dashboard_db.query(Dashboard).filter(Dashboard.title == "User Check").first()
        assert row is not None
        assert row.user_id == test_user.id

    @pytest.mark.asyncio
    async def test_auto_generates_integer_id(self, dashboard_db, test_user):
        payload = DashboardCreate(title="Auto ID")

        result = await create_dashboard(payload=payload, db=dashboard_db, current_user=test_user)

        assert isinstance(result.id, int)
        assert result.id > 0


# ---------------------------------------------------------------------------
# TestUpdateDashboard
# ---------------------------------------------------------------------------

class TestUpdateDashboard:
    """Tests for update_dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_update_title_only(self, dashboard_db, test_user):
        d = _make_dashboard(dashboard_db, test_user.id, title="Old Title", description="Keep")

        payload = DashboardUpdate(title="New Title")
        result = await update_dashboard(
            dashboard_id=d.id, payload=payload, db=dashboard_db, current_user=test_user,
        )

        assert result.title == "New Title"
        assert result.description == "Keep"

    @pytest.mark.asyncio
    async def test_update_description_only(self, dashboard_db, test_user):
        d = _make_dashboard(dashboard_db, test_user.id, title="Keep Title")

        payload = DashboardUpdate(description="New Desc")
        result = await update_dashboard(
            dashboard_id=d.id, payload=payload, db=dashboard_db, current_user=test_user,
        )

        assert result.title == "Keep Title"
        assert result.description == "New Desc"

    @pytest.mark.asyncio
    async def test_update_widgets_only(self, dashboard_db, test_user):
        d = _make_dashboard(dashboard_db, test_user.id, title="W", widgets=[{"old": True}])

        new_widgets = [{"new": True}, {"also_new": True}]
        payload = DashboardUpdate(widgets=new_widgets)
        result = await update_dashboard(
            dashboard_id=d.id, payload=payload, db=dashboard_db, current_user=test_user,
        )

        assert result.widgets == new_widgets
        assert result.title == "W"

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, dashboard_db, test_user):
        payload = DashboardUpdate(title="Ghost")

        with pytest.raises(HTTPException) as exc_info:
            await update_dashboard(
                dashboard_id=99999, payload=payload, db=dashboard_db, current_user=test_user,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_all_fields(self, dashboard_db, test_user):
        d = _make_dashboard(
            dashboard_db, test_user.id,
            title="Old", description="Old Desc", widgets=[{"v": 1}],
        )

        payload = DashboardUpdate(title="New", description="New Desc", widgets=[{"v": 2}])
        result = await update_dashboard(
            dashboard_id=d.id, payload=payload, db=dashboard_db, current_user=test_user,
        )

        assert result.title == "New"
        assert result.description == "New Desc"
        assert result.widgets == [{"v": 2}]


# ---------------------------------------------------------------------------
# TestDeleteDashboard
# ---------------------------------------------------------------------------

class TestDeleteDashboard:
    """Tests for delete_dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_success_removes_from_db(self, dashboard_db, test_user):
        d = _make_dashboard(dashboard_db, test_user.id, title="Delete Me")
        dashboard_id = d.id

        await delete_dashboard(dashboard_id=dashboard_id, db=dashboard_db, current_user=test_user)

        assert dashboard_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first() is None

    @pytest.mark.asyncio
    async def test_not_found_returns_404(self, dashboard_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            await delete_dashboard(dashboard_id=99999, db=dashboard_db, current_user=test_user)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_user_returns_404(self, dashboard_db, test_user):
        other_user = User(id="user-del-other", email="del-other@example.com", auth_provider="sso")
        dashboard_db.add(other_user)
        dashboard_db.commit()

        d = _make_dashboard(dashboard_db, other_user.id, title="Not Yours To Delete")

        with pytest.raises(HTTPException) as exc_info:
            await delete_dashboard(dashboard_id=d.id, db=dashboard_db, current_user=test_user)

        assert exc_info.value.status_code == 404
        # Dashboard should still exist
        assert dashboard_db.query(Dashboard).filter(Dashboard.id == d.id).first() is not None

    @pytest.mark.asyncio
    async def test_returns_none(self, dashboard_db, test_user):
        """delete_dashboard should return None (204 no content)."""
        d = _make_dashboard(dashboard_db, test_user.id, title="Return None")

        result = await delete_dashboard(dashboard_id=d.id, db=dashboard_db, current_user=test_user)

        assert result is None
