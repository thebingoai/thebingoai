import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from backend.services import briefing_runner


def test_run_returns_failed_status_when_orchestrator_raises():
    briefing = MagicMock(id=1, user_id="u1", dashboard_id=10, status="generating", error=None)
    user = MagicMock(id="u1")
    dashboard = MagicMock(id=10, date_range_from=None, date_range_to=None)

    db = MagicMock()
    queries = {"Briefing": briefing, "Dashboard": dashboard, "User": user}
    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = queries.get(model.__name__)
        return q
    db.query.side_effect = query_side_effect

    with patch("backend.services.briefing_runner.SessionLocal", return_value=db), \
         patch("backend.services.briefing_runner.build_orchestrator_context", new=AsyncMock(side_effect=RuntimeError("boom"))):
        asyncio.run(briefing_runner.run(briefing_id=1))

    assert briefing.status == "failed"
    assert "boom" in (briefing.error or "")


def test_run_invokes_orchestrator_with_briefing_context():
    briefing = MagicMock(id=1, user_id="u1", dashboard_id=10, status="generating")
    dashboard = MagicMock(id=10, date_range_from=None, date_range_to=None)
    user = MagicMock(id="u1")

    db = MagicMock()
    queries = {"Briefing": briefing, "Dashboard": dashboard, "User": user}
    def query_side_effect(model):
        q = MagicMock()
        q.filter.return_value.first.return_value = queries.get(model.__name__)
        return q
    db.query.side_effect = query_side_effect

    fake_ctx = MagicMock(agent_context=MagicMock(), custom_agents=None,
                         memory_context="", user_skills=None,
                         user_memories_context="", soul_prompt="", skill_suggestions=None)

    with patch("backend.services.briefing_runner.SessionLocal", return_value=db), \
         patch("backend.services.briefing_runner.build_orchestrator_context", new=AsyncMock(return_value=fake_ctx)) as build_ctx, \
         patch("backend.services.briefing_runner.run_orchestrator", new=AsyncMock(return_value={"success": True})) as run_orch:
        asyncio.run(briefing_runner.run(briefing_id=1))

    assert build_ctx.await_count == 1
    assert run_orch.await_count == 1
    assert fake_ctx.agent_context.briefing_id == 1
