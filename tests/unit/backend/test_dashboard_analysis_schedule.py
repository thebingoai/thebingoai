"""Unit tests for analysis-schedule endpoints in backend.api.dashboard_schedule."""

import sys
from datetime import datetime
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401 — resolve relationship mappers

from backend.api.dashboard_schedule import (
    set_analysis_schedule,
    remove_analysis_schedule,
)
from backend.schemas.dashboard_schedule import DashboardScheduleUpdate


# ---------------------------------------------------------------------------
# Ensure croniter is importable even if not installed
# ---------------------------------------------------------------------------

def _ensure_croniter_stub():
    if "croniter" not in sys.modules:
        mod = ModuleType("croniter")
        mod.croniter = MagicMock()
        sys.modules["croniter"] = mod


_ensure_croniter_stub()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analysis_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        Dashboard.__table__,
        HeartbeatJob.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def test_user(analysis_db):
    user = User(id="user-1", email="test@example.com", auth_provider="sso")
    analysis_db.add(user)
    analysis_db.commit()
    return user


@pytest.fixture
def test_dashboard(analysis_db, test_user):
    d = Dashboard(user_id=test_user.id, title="Sales Dashboard", widgets=[])
    analysis_db.add(d)
    analysis_db.commit()
    analysis_db.refresh(d)
    return d


def _fake_croniter(next_dt: datetime):
    mock_instance = MagicMock()
    mock_instance.get_next.return_value = next_dt
    return mock_instance


# ---------------------------------------------------------------------------
# TestSetAnalysisSchedule
# ---------------------------------------------------------------------------

class TestSetAnalysisSchedule:
    """POST /{dashboard_id}/analysis-schedule — creates or updates a HeartbeatJob."""

    @pytest.mark.asyncio
    async def test_creates_heartbeat_job(self, analysis_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")
        fake_next = datetime(2026, 4, 24, 8, 0, 0)

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        job = analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).first()
        assert job is not None
        assert f"Sales Dashboard" in job.name
        assert str(test_dashboard.id) in job.prompt
        assert job.cron_expression == "0 8 * * *"
        assert job.is_active is True
        assert job.next_run_at == fake_next

    @pytest.mark.asyncio
    async def test_returns_job_metadata(self, analysis_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1w")
        fake_next = datetime(2026, 4, 28, 0, 0, 0)

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 0 * * 1"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            result = await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        assert result["dashboard_id"] == test_dashboard.id
        assert "job_id" in result
        assert result["schedule_type"] == "preset"
        assert result["schedule_value"] == "1w"
        assert result["is_active"] is True
        assert result["next_run_at"] is not None

    @pytest.mark.asyncio
    async def test_updates_existing_job_instead_of_creating_duplicate(self, analysis_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")
        fake_next = datetime(2026, 4, 24, 8, 0, 0)

        # Create twice — should not duplicate
        for _ in range(2):
            with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
                 patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
                await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        count = analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_update_changes_schedule_fields(self, analysis_db, test_user, test_dashboard):
        fake_next = datetime(2026, 4, 24, 8, 0, 0)

        # Create with daily
        payload_daily = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")
        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            await set_analysis_schedule(test_dashboard.id, payload_daily, test_user, analysis_db)

        # Update to weekly
        payload_weekly = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1w")
        new_next = datetime(2026, 4, 28, 0, 0, 0)
        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 0 * * 1"), \
             patch("croniter.croniter", return_value=_fake_croniter(new_next)):
            await set_analysis_schedule(test_dashboard.id, payload_weekly, test_user, analysis_db)

        job = analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).first()
        assert job.cron_expression == "0 0 * * 1"
        assert job.schedule_value == "1w"
        assert job.next_run_at == new_next

    @pytest.mark.asyncio
    async def test_invalid_schedule_raises_400(self, analysis_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="bad")

        with patch("backend.schemas.heartbeat.resolve_cron_expression", side_effect=ValueError("Unknown preset")):
            with pytest.raises(HTTPException) as exc_info:
                await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        assert exc_info.value.status_code == 400
        assert "Unknown preset" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, analysis_db, test_user):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"):
            with pytest.raises(HTTPException) as exc_info:
                await set_analysis_schedule(9999, payload, test_user, analysis_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_wrong_user_dashboard_raises_404(self, analysis_db, test_user, test_dashboard):
        other_user = User(id="user-other", email="other@example.com", auth_provider="sso")
        analysis_db.add(other_user)
        analysis_db.commit()

        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"):
            with pytest.raises(HTTPException) as exc_info:
                await set_analysis_schedule(test_dashboard.id, payload, other_user, analysis_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_job_prompt_references_dashboard_id(self, analysis_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")
        fake_next = datetime(2026, 4, 24, 8, 0, 0)

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        job = analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).first()
        assert str(test_dashboard.id) in job.prompt
        assert "analyze" in job.prompt.lower()

    @pytest.mark.asyncio
    async def test_agent_type_is_none_for_orchestrator(self, analysis_db, test_user, test_dashboard):
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")
        fake_next = datetime(2026, 4, 24, 8, 0, 0)

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        job = analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).first()
        assert job.agent_type is None


# ---------------------------------------------------------------------------
# TestRemoveAnalysisSchedule
# ---------------------------------------------------------------------------

class TestRemoveAnalysisSchedule:
    """DELETE /{dashboard_id}/analysis-schedule — removes the HeartbeatJob."""

    @pytest.mark.asyncio
    async def test_removes_existing_job(self, analysis_db, test_user, test_dashboard):
        fake_next = datetime(2026, 4, 24, 8, 0, 0)
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            await set_analysis_schedule(test_dashboard.id, payload, test_user, analysis_db)

        # Verify it was created
        assert analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).count() == 1

        await remove_analysis_schedule(test_dashboard.id, test_user, analysis_db)

        assert analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == test_user.id).count() == 0

    @pytest.mark.asyncio
    async def test_idempotent_when_no_job_exists(self, analysis_db, test_user, test_dashboard):
        # Should not raise even if no job exists
        await remove_analysis_schedule(test_dashboard.id, test_user, analysis_db)

    @pytest.mark.asyncio
    async def test_dashboard_not_found_raises_404(self, analysis_db, test_user):
        with pytest.raises(HTTPException) as exc_info:
            await remove_analysis_schedule(9999, test_user, analysis_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_does_not_remove_other_users_job(self, analysis_db, test_user, test_dashboard):
        other_user = User(id="user-2", email="other@example.com", auth_provider="sso")
        analysis_db.add(other_user)
        other_dash = Dashboard(user_id=other_user.id, title="Sales Dashboard", widgets=[])
        analysis_db.add(other_dash)
        analysis_db.commit()
        analysis_db.refresh(other_dash)

        fake_next = datetime(2026, 4, 24, 8, 0, 0)
        payload = DashboardScheduleUpdate.model_construct(schedule_type="preset", schedule_value="1d")

        with patch("backend.schemas.heartbeat.resolve_cron_expression", return_value="0 8 * * *"), \
             patch("croniter.croniter", return_value=_fake_croniter(fake_next)):
            await set_analysis_schedule(other_dash.id, payload, other_user, analysis_db)

        # test_user tries to delete — their dashboard lookup will fail (404)
        with pytest.raises(HTTPException) as exc_info:
            await remove_analysis_schedule(other_dash.id, test_user, analysis_db)
        assert exc_info.value.status_code == 404

        # Other user's job should still exist
        assert analysis_db.query(HeartbeatJob).filter(HeartbeatJob.user_id == other_user.id).count() == 1

    @pytest.mark.asyncio
    async def test_returns_none(self, analysis_db, test_user, test_dashboard):
        result = await remove_analysis_schedule(test_dashboard.id, test_user, analysis_db)
        assert result is None
