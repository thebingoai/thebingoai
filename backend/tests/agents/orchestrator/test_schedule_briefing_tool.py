"""
Unit tests for schedule_briefing tool.

Verifies that calling the tool:
- Creates a HeartbeatJob with kind='briefing' for a valid dashboard
- Correctly resolves a partial dashboard name match
- Updates an existing job rather than creating a duplicate
- Rejects invalid cron expressions
- Rejects ambiguous (multiple) dashboard name matches
- Returns an error when no dashboard matches
"""
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agents.context import AgentContext
from backend.agents.orchestrator.schedule_briefing_tool import build_schedule_briefing_tool
from backend.models.dashboard import Dashboard
from backend.models.heartbeat_job import HeartbeatJob


# ── Fixture helpers ────────────────────────────────────────────────────

@pytest.fixture
def agent_context(sample_user):
    return AgentContext(
        user_id=sample_user.id,
        available_connections=[],
        connection_metadata=[],
    )


def get_tool(agent_context, db_session):
    """Return the unwrapped schedule_briefing tool callable."""
    tools = build_schedule_briefing_tool(agent_context, lambda: db_session)
    assert len(tools) == 1
    return tools[0]


# ── Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_creates_heartbeat_job_for_valid_dashboard(db_session, sample_user, sample_dashboard):
    ctx = AgentContext(user_id=sample_user.id, available_connections=[], connection_metadata=[])
    tool = get_tool(ctx, db_session)

    result = json.loads(await tool.ainvoke({"dashboard_name": sample_dashboard.title[:10], "cron": "0 9 * * 1"}))

    assert result["success"] is True
    assert result["dashboard_id"] == sample_dashboard.id
    assert result["cron_expression"] == "0 9 * * 1"
    assert "next_run_at" in result
    assert "job_id" in result

    job = db_session.query(HeartbeatJob).filter(HeartbeatJob.id == result["job_id"]).first()
    assert job is not None
    assert job.kind == "briefing"
    assert job.is_active is True
    assert job.cron_expression == "0 9 * * 1"
    assert str(sample_dashboard.id) in job.prompt


@pytest.mark.asyncio
async def test_updates_existing_job_instead_of_creating_duplicate(db_session, sample_user, sample_dashboard):
    ctx = AgentContext(user_id=sample_user.id, available_connections=[], connection_metadata=[])
    tool = get_tool(ctx, db_session)

    r1 = json.loads(await tool.ainvoke({"dashboard_name": sample_dashboard.title, "cron": "0 9 * * *"}))
    assert r1["success"] is True
    job_id_1 = r1["job_id"]

    r2 = json.loads(await tool.ainvoke({"dashboard_name": sample_dashboard.title, "cron": "0 18 * * *"}))
    assert r2["success"] is True

    # Same job, updated cron
    assert r2["job_id"] == job_id_1
    job = db_session.query(HeartbeatJob).filter(HeartbeatJob.id == job_id_1).first()
    assert job.cron_expression == "0 18 * * *"
    assert db_session.query(HeartbeatJob).filter(HeartbeatJob.user_id == sample_user.id).count() == 1


@pytest.mark.asyncio
async def test_rejects_invalid_cron(db_session, sample_user, sample_dashboard):
    ctx = AgentContext(user_id=sample_user.id, available_connections=[], connection_metadata=[])
    tool = get_tool(ctx, db_session)

    result = json.loads(await tool.ainvoke({"dashboard_name": sample_dashboard.title, "cron": "not-a-cron"}))

    assert result["success"] is False
    assert "cron" in result["message"].lower() or "invalid" in result["message"].lower()
    # No job created for this user+dashboard
    assert db_session.query(HeartbeatJob).filter(
        HeartbeatJob.user_id == sample_user.id,
    ).count() == 0


@pytest.mark.asyncio
async def test_returns_error_when_no_dashboard_matches(db_session, sample_user):
    ctx = AgentContext(user_id=sample_user.id, available_connections=[], connection_metadata=[])
    tool = get_tool(ctx, db_session)

    result = json.loads(await tool.ainvoke({"dashboard_name": "Nonexistent Dashboard XYZ", "cron": "0 9 * * *"}))

    assert result["success"] is False
    assert "no dashboard" in result["message"].lower()


@pytest.mark.asyncio
async def test_returns_error_when_multiple_dashboards_match(db_session, sample_user):
    # Create two dashboards with similar names
    d1 = Dashboard(user_id=sample_user.id, title="Sales Weekly Report", widgets=[])
    d2 = Dashboard(user_id=sample_user.id, title="Sales Monthly Report", widgets=[])
    db_session.add_all([d1, d2])
    db_session.commit()

    ctx = AgentContext(user_id=sample_user.id, available_connections=[], connection_metadata=[])
    tool = get_tool(ctx, db_session)

    result = json.loads(await tool.ainvoke({"dashboard_name": "Sales", "cron": "0 9 * * *"}))

    assert result["success"] is False
    assert "multiple" in result["message"].lower()
    assert "Sales Weekly Report" in result["message"]
    assert "Sales Monthly Report" in result["message"]


@pytest.mark.asyncio
async def test_job_only_sees_own_users_dashboards(db_session, sample_user, other_user, sample_dashboard):
    """A user cannot schedule briefings for another user's dashboards."""
    # sample_dashboard belongs to sample_user; other_user should not find it
    ctx = AgentContext(user_id=other_user.id, available_connections=[], connection_metadata=[])
    tool = get_tool(ctx, db_session)

    result = json.loads(await tool.ainvoke({"dashboard_name": sample_dashboard.title, "cron": "0 9 * * *"}))

    assert result["success"] is False
    assert "no dashboard" in result["message"].lower()
