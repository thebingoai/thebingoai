"""Unit tests for POST /dashboards/{id}/analyze endpoint."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401

from backend.api.dashboard_analyze import analyze_dashboard


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        Dashboard.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(db):
    u = User(id="user-1", email="test@example.com", auth_provider="sso")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def dashboard(db, user):
    d = Dashboard(user_id=user.id, title="Sales Dashboard", widgets=[])
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _mock_ctx():
    ctx = MagicMock()
    ctx.agent_context = MagicMock()
    ctx.custom_agents = []
    ctx.memory_context = ""
    ctx.user_skills = []
    ctx.user_memories_context = ""
    ctx.soul_prompt = ""
    ctx.skill_suggestions = []
    return ctx


# ---------------------------------------------------------------------------
# TestAnalyzeDashboardNotFound
# ---------------------------------------------------------------------------

class TestAnalyzeDashboardNotFound:
    @pytest.mark.asyncio
    async def test_missing_dashboard_raises_404(self, db, user):
        with pytest.raises(HTTPException) as exc_info:
            await analyze_dashboard(9999, current_user=user, db=db)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Dashboard not found"

    @pytest.mark.asyncio
    async def test_wrong_user_raises_404(self, db, dashboard):
        other = User(id="user-2", email="other@example.com", auth_provider="sso")
        db.add(other)
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            await analyze_dashboard(dashboard.id, current_user=other, db=db)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestAnalyzeDashboardSuccess
# ---------------------------------------------------------------------------

class TestAnalyzeDashboardSuccess:
    @pytest.mark.asyncio
    async def test_returns_success_with_message(self, db, user, dashboard):
        ctx = _mock_ctx()
        orchestrator_result = {"message": "Revenue is up 15% month-over-month."}

        with patch("backend.services.heartbeat_context.build_orchestrator_context", new=AsyncMock(return_value=ctx)), \
             patch("backend.agents.run_orchestrator", new=AsyncMock(return_value=orchestrator_result)):
            result = await analyze_dashboard(dashboard.id, current_user=user, db=db)

        assert result["success"] is True
        assert result["dashboard_id"] == dashboard.id
        assert result["message"] == "Revenue is up 15% month-over-month."

    @pytest.mark.asyncio
    async def test_empty_orchestrator_message_returns_empty_string(self, db, user, dashboard):
        ctx = _mock_ctx()

        with patch("backend.services.heartbeat_context.build_orchestrator_context", new=AsyncMock(return_value=ctx)), \
             patch("backend.agents.run_orchestrator", new=AsyncMock(return_value={})):
            result = await analyze_dashboard(dashboard.id, current_user=user, db=db)

        assert result["success"] is True
        assert result["message"] == ""

    @pytest.mark.asyncio
    async def test_prompt_references_dashboard_id(self, db, user, dashboard):
        ctx = _mock_ctx()
        captured_prompts = []

        async def _capture(**kwargs):
            captured_prompts.append(kwargs.get("user_question", ""))
            return {"message": "ok"}

        with patch("backend.services.heartbeat_context.build_orchestrator_context", new=AsyncMock(return_value=ctx)), \
             patch("backend.agents.run_orchestrator", new=_capture):
            await analyze_dashboard(dashboard.id, current_user=user, db=db)

        assert len(captured_prompts) == 1
        assert str(dashboard.id) in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_orchestrator_called_with_empty_history(self, db, user, dashboard):
        ctx = _mock_ctx()
        mock_run = AsyncMock(return_value={"message": "done"})

        with patch("backend.services.heartbeat_context.build_orchestrator_context", new=AsyncMock(return_value=ctx)), \
             patch("backend.agents.run_orchestrator", mock_run):
            await analyze_dashboard(dashboard.id, current_user=user, db=db)

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["history"] == []

    @pytest.mark.asyncio
    async def test_context_built_with_correct_user(self, db, user, dashboard):
        ctx = _mock_ctx()
        mock_build = AsyncMock(return_value=ctx)

        with patch("backend.services.heartbeat_context.build_orchestrator_context", mock_build), \
             patch("backend.agents.run_orchestrator", new=AsyncMock(return_value={"message": ""})):
            await analyze_dashboard(dashboard.id, current_user=user, db=db)

        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["user"] is user


# ---------------------------------------------------------------------------
# TestAnalyzeDashboardErrors
# ---------------------------------------------------------------------------

class TestAnalyzeDashboardErrors:
    @pytest.mark.asyncio
    async def test_context_build_failure_raises_500(self, db, user, dashboard):
        with patch("backend.services.heartbeat_context.build_orchestrator_context",
                   new=AsyncMock(side_effect=Exception("Redis down"))):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_dashboard(dashboard.id, current_user=user, db=db)
        assert exc_info.value.status_code == 500
        assert "initialize" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_orchestrator_failure_raises_500(self, db, user, dashboard):
        ctx = _mock_ctx()

        with patch("backend.services.heartbeat_context.build_orchestrator_context", new=AsyncMock(return_value=ctx)), \
             patch("backend.agents.run_orchestrator",
                   new=AsyncMock(side_effect=Exception("LLM timeout"))):
            with pytest.raises(HTTPException) as exc_info:
                await analyze_dashboard(dashboard.id, current_user=user, db=db)
        assert exc_info.value.status_code == 500
        assert "Analysis failed" in exc_info.value.detail
