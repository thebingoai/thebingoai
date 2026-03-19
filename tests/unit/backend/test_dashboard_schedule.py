"""Unit tests for backend.api.dashboard_schedule — schedule CRUD + refresh runs."""

import sys
from datetime import datetime, timedelta
from types import ModuleType
from unittest.mock import MagicMock, patch

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

from backend.api.dashboard_schedule import (
    _get_dashboard_or_404,
    set_schedule,
    toggle_schedule,
    remove_schedule,
    list_refresh_runs,
    trigger_refresh,
)
from backend.schemas.dashboard_schedule import (
    DashboardScheduleUpdate,
    DashboardScheduleToggle,
    DashboardScheduleResponse,
    DashboardRefreshRunListResponse,
)


# ---------------------------------------------------------------------------
# Helpers — ensure 'croniter' module is importable even if not installed
# ---------------------------------------------------------------------------

def _ensure_croniter_stub():
    """Install a stub ``croniter`` package in sys.modules if the real one is absent."""
    if "croniter" not in sys.modules:
        mod = ModuleType("croniter")
        mod.croniter = MagicMock()  # placeholder; tests patch over this
        sys.modules["croniter"] = mod


_ensure_croniter_stub()


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


@pytest.fixture
def test_dashboard(dashboard_db, test_user):
    d = Dashboard(user_id=test_user.id, title="Test Dashboard", widgets=[])
    dashboard_db.add(d)
    dashboard_db.commit()
    dashboard_db.refresh(d)
    return d


# ---------------------------------------------------------------------------
# TestGetDashboardOr404
# ---------------------------------------------------------------------------

class TestGetDashboardOr404:
    """Tests for _get_dashboard_or_404 helper."""

    def test_found_returns_dashboard(self, dashboard_db, test_user, test_dashboard):
        result = _get_dashboard_or_404(test_dashboard.id, test_user.id, dashboard_db)
        assert result.id == test_dashboard.id
        assert result.title == "Test Dashboard"

    def test_not_found_raises_404(self, dashboard_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            _get_dashboard_or_404(9999, test_user.id, dashboard_db)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Dashboard not found"

    def test_wrong_user_raises_404(self, dashboard_db, test_dashboard):
        with pytest.raises(HTTPException) as exc_info:
            _get_dashboard_or_404(test_dashboard.id, "other-user", dashboard_db)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Dashboard not found"


# ---------------------------------------------------------------------------
# TestSetSchedule
# ---------------------------------------------------------------------------

class TestSetSchedule:
    """Tests for PUT /{dashboard_id}/schedule."""

    @pytest.mark.asyncio
    async def test_sets_schedule_fields_and_activates(self, dashboard_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1h")
        fake_next = datetime(2026, 4, 1, 12, 0, 0)

        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = fake_next

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 * * * *"), \
             patch("croniter.croniter", return_value=mock_croniter_instance):
            result = await set_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert isinstance(result, DashboardScheduleResponse)
        assert test_dashboard.schedule_type == "preset"
        assert test_dashboard.schedule_value == "1h"
        assert test_dashboard.cron_expression == "0 * * * *"
        assert test_dashboard.schedule_active is True

    @pytest.mark.asyncio
    async def test_custom_cron_expression_works(self, dashboard_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="cron", schedule_value="*/5 * * * *")
        fake_next = datetime(2026, 4, 1, 12, 5, 0)

        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = fake_next

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="*/5 * * * *"), \
             patch("croniter.croniter", return_value=mock_croniter_instance):
            result = await set_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert test_dashboard.cron_expression == "*/5 * * * *"
        assert test_dashboard.schedule_type == "cron"

    @pytest.mark.asyncio
    async def test_invalid_schedule_raises_400(self, dashboard_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="bad")

        with patch("backend.schemas.heartbeat.resolve_cron_expression", side_effect=ValueError("Unknown preset")):
            with pytest.raises(HTTPException) as exc_info:
                await set_schedule(test_dashboard.id, payload, test_user, dashboard_db)
        assert exc_info.value.status_code == 400
        assert "Unknown preset" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_computes_next_run_at_via_croniter(self, dashboard_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1h")
        expected_next = datetime(2026, 5, 1, 10, 0, 0)

        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = expected_next

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 * * * *"), \
             patch("croniter.croniter", return_value=mock_croniter_instance) as mock_cron_cls:
            await set_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        mock_cron_cls.assert_called_once()
        mock_croniter_instance.get_next.assert_called_once_with(datetime)
        assert test_dashboard.next_run_at == expected_next

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, dashboard_db, test_user):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1h")

        with pytest.raises(HTTPException) as exc_info:
            await set_schedule(9999, payload, test_user, dashboard_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_dashboard_schedule_response_with_correct_fields(self, dashboard_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1h")
        fake_next = datetime(2026, 4, 1, 12, 0, 0)

        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = fake_next

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 * * * *"), \
             patch("croniter.croniter", return_value=mock_croniter_instance):
            result = await set_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert isinstance(result, DashboardScheduleResponse)
        assert result.schedule_type == "preset"
        assert result.schedule_value == "1h"
        assert result.cron_expression == "0 * * * *"
        assert result.schedule_active is True
        assert result.next_run_at == fake_next


# ---------------------------------------------------------------------------
# TestToggleSchedule
# ---------------------------------------------------------------------------

class TestToggleSchedule:
    """Tests for PATCH /{dashboard_id}/schedule."""

    @pytest.mark.asyncio
    async def test_activate_recomputes_next_run_at(self, dashboard_db, test_user, test_dashboard):
        test_dashboard.cron_expression = "0 * * * *"
        test_dashboard.schedule_active = False
        dashboard_db.commit()

        payload = DashboardScheduleToggle(schedule_active=True)
        expected_next = datetime(2026, 4, 1, 13, 0, 0)

        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = expected_next

        with patch("croniter.croniter", return_value=mock_croniter_instance):
            result = await toggle_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert result.schedule_active is True
        assert test_dashboard.next_run_at == expected_next

    @pytest.mark.asyncio
    async def test_deactivate_sets_schedule_active_false(self, dashboard_db, test_user, test_dashboard):
        test_dashboard.cron_expression = "0 * * * *"
        test_dashboard.schedule_active = True
        dashboard_db.commit()

        payload = DashboardScheduleToggle(schedule_active=False)

        with patch("croniter.croniter"):
            result = await toggle_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert result.schedule_active is False
        assert test_dashboard.schedule_active is False

    @pytest.mark.asyncio
    async def test_no_cron_configured_raises_400(self, dashboard_db, test_user, test_dashboard):
        test_dashboard.cron_expression = None
        dashboard_db.commit()

        payload = DashboardScheduleToggle(schedule_active=True)

        with patch("croniter.croniter"):
            with pytest.raises(HTTPException) as exc_info:
                await toggle_schedule(test_dashboard.id, payload, test_user, dashboard_db)
        assert exc_info.value.status_code == 400
        assert "no schedule configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, dashboard_db, test_user):
        payload = DashboardScheduleToggle(schedule_active=True)

        with patch("croniter.croniter"):
            with pytest.raises(HTTPException) as exc_info:
                await toggle_schedule(9999, payload, test_user, dashboard_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_reactivation_recomputes_next_run_at(self, dashboard_db, test_user, test_dashboard):
        old_next = datetime(2026, 1, 1, 0, 0, 0)
        test_dashboard.cron_expression = "0 */2 * * *"
        test_dashboard.schedule_active = False
        test_dashboard.next_run_at = old_next
        dashboard_db.commit()

        payload = DashboardScheduleToggle(schedule_active=True)
        new_next = datetime(2026, 6, 1, 14, 0, 0)

        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = new_next

        with patch("croniter.croniter", return_value=mock_croniter_instance):
            result = await toggle_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert test_dashboard.next_run_at == new_next
        assert test_dashboard.next_run_at != old_next

    @pytest.mark.asyncio
    async def test_returns_dashboard_schedule_response(self, dashboard_db, test_user, test_dashboard):
        test_dashboard.cron_expression = "0 9 * * *"
        test_dashboard.schedule_type = "preset"
        test_dashboard.schedule_value = "daily"
        test_dashboard.schedule_active = True
        dashboard_db.commit()

        payload = DashboardScheduleToggle(schedule_active=False)

        with patch("croniter.croniter"):
            result = await toggle_schedule(test_dashboard.id, payload, test_user, dashboard_db)

        assert isinstance(result, DashboardScheduleResponse)
        assert result.schedule_active is False
        assert result.cron_expression == "0 9 * * *"
        assert result.schedule_type == "preset"


# ---------------------------------------------------------------------------
# TestRemoveSchedule
# ---------------------------------------------------------------------------

class TestRemoveSchedule:
    """Tests for DELETE /{dashboard_id}/schedule."""

    @pytest.mark.asyncio
    async def test_nullifies_all_schedule_fields(self, dashboard_db, test_user, test_dashboard):
        test_dashboard.schedule_type = "preset"
        test_dashboard.schedule_value = "1h"
        test_dashboard.cron_expression = "0 * * * *"
        test_dashboard.schedule_active = True
        test_dashboard.next_run_at = datetime(2026, 4, 1, 12, 0, 0)
        dashboard_db.commit()

        await remove_schedule(test_dashboard.id, test_user, dashboard_db)

        dashboard_db.refresh(test_dashboard)
        assert test_dashboard.schedule_type is None
        assert test_dashboard.schedule_value is None
        assert test_dashboard.cron_expression is None
        assert test_dashboard.schedule_active is False
        assert test_dashboard.next_run_at is None

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, dashboard_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            await remove_schedule(9999, test_user, dashboard_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_idempotent_on_unscheduled_dashboard(self, dashboard_db, test_user, test_dashboard):
        # Dashboard already has no schedule — should not raise
        await remove_schedule(test_dashboard.id, test_user, dashboard_db)

        dashboard_db.refresh(test_dashboard)
        assert test_dashboard.schedule_type is None
        assert test_dashboard.schedule_active is False

    @pytest.mark.asyncio
    async def test_returns_none(self, dashboard_db, test_user, test_dashboard):
        result = await remove_schedule(test_dashboard.id, test_user, dashboard_db)
        assert result is None


# ---------------------------------------------------------------------------
# TestListRefreshRuns
# ---------------------------------------------------------------------------

class TestListRefreshRuns:
    """Tests for GET /{dashboard_id}/schedule/runs."""

    @pytest.mark.asyncio
    async def test_returns_runs_with_total(self, dashboard_db, test_user, test_dashboard):
        now = datetime.utcnow()
        run1 = DashboardRefreshRun(
            id="run-1", dashboard_id=test_dashboard.id, status="completed",
            started_at=now - timedelta(hours=2), widgets_total=3, widgets_succeeded=3, widgets_failed=0,
        )
        run2 = DashboardRefreshRun(
            id="run-2", dashboard_id=test_dashboard.id, status="running",
            started_at=now - timedelta(hours=1), widgets_total=5, widgets_succeeded=2, widgets_failed=0,
        )
        dashboard_db.add_all([run1, run2])
        dashboard_db.commit()

        result = await list_refresh_runs(test_dashboard.id, limit=20, offset=0,
                                         current_user=test_user, db=dashboard_db)

        assert isinstance(result, DashboardRefreshRunListResponse)
        assert result.total == 2
        assert len(result.runs) == 2

    @pytest.mark.asyncio
    async def test_empty_returns_zero_total(self, dashboard_db, test_user, test_dashboard):
        result = await list_refresh_runs(test_dashboard.id, limit=20, offset=0,
                                         current_user=test_user, db=dashboard_db)

        assert result.total == 0
        assert result.runs == []

    @pytest.mark.asyncio
    async def test_pagination_limit_and_offset(self, dashboard_db, test_user, test_dashboard):
        now = datetime.utcnow()
        for i in range(5):
            run = DashboardRefreshRun(
                id=f"run-{i}", dashboard_id=test_dashboard.id, status="completed",
                started_at=now - timedelta(hours=5 - i),
                widgets_total=1, widgets_succeeded=1, widgets_failed=0,
            )
            dashboard_db.add(run)
        dashboard_db.commit()

        # Request page of 2, offset 1
        result = await list_refresh_runs(test_dashboard.id, limit=2, offset=1,
                                         current_user=test_user, db=dashboard_db)

        assert result.total == 5
        assert len(result.runs) == 2

    @pytest.mark.asyncio
    async def test_ordered_desc_by_started_at(self, dashboard_db, test_user, test_dashboard):
        now = datetime.utcnow()
        early = DashboardRefreshRun(
            id="run-early", dashboard_id=test_dashboard.id, status="completed",
            started_at=now - timedelta(hours=3),
            widgets_total=1, widgets_succeeded=1, widgets_failed=0,
        )
        late = DashboardRefreshRun(
            id="run-late", dashboard_id=test_dashboard.id, status="completed",
            started_at=now - timedelta(minutes=10),
            widgets_total=1, widgets_succeeded=1, widgets_failed=0,
        )
        dashboard_db.add_all([early, late])
        dashboard_db.commit()

        result = await list_refresh_runs(test_dashboard.id, limit=20, offset=0,
                                         current_user=test_user, db=dashboard_db)

        assert result.runs[0].id == "run-late"
        assert result.runs[1].id == "run-early"

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, dashboard_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            await list_refresh_runs(9999, limit=20, offset=0,
                                    current_user=test_user, db=dashboard_db)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestTriggerRefresh
# ---------------------------------------------------------------------------

class TestTriggerRefresh:
    """Tests for POST /{dashboard_id}/schedule/run."""

    @pytest.mark.asyncio
    async def test_dispatches_delay_with_dashboard_id(self, dashboard_db, test_user, test_dashboard):
        with patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            await trigger_refresh(test_dashboard.id, test_user, dashboard_db)
            mock_task.delay.assert_called_once_with(test_dashboard.id)

    @pytest.mark.asyncio
    async def test_returns_queued_true_and_dashboard_id(self, dashboard_db, test_user, test_dashboard):
        with patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh"):
            result = await trigger_refresh(test_dashboard.id, test_user, dashboard_db)

        assert result == {"queued": True, "dashboard_id": test_dashboard.id}

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, dashboard_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            await trigger_refresh(9999, test_user, dashboard_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_delay_called_exactly_once(self, dashboard_db, test_user, test_dashboard):
        with patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            await trigger_refresh(test_dashboard.id, test_user, dashboard_db)
            assert mock_task.delay.call_count == 1
