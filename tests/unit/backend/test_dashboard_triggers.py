"""Unit tests for Phase 4 — Trigger Materialization on Dashboard Create/Update.

Tests cover:
- create_dashboard dispatches materialization task
- update_dashboard dispatches task when SQL changes
- update_dashboard does NOT dispatch task on cosmetic-only changes
- POST /dashboards/{id}/materialize returns 202
- Manual materialize rate limit (second request within 5 min returns 429)
- Manual materialize checks dashboard ownership
- Inline _execute_widget_sql still works alongside async materialization
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.connectors.base import QueryResult
from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401 — resolve relationship mappers


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


def _make_context(user_id="user-1"):
    """Create a mock AgentContext."""
    ctx = MagicMock()
    ctx.user_id = user_id
    ctx.can_access_connection = MagicMock(return_value=True)
    return ctx


def _make_widget(widget_id, sql="SELECT 1", connection_id=1):
    """Build a minimal widget dict with dataSource."""
    return {
        "id": widget_id,
        "position": {"x": 0, "y": 0, "w": 6, "h": 4},
        "widget": {"type": "kpi", "config": {"label": "Test"}},
        "dataSource": {
            "connectionId": connection_id,
            "sql": sql,
            "mapping": {"type": "kpi", "valueColumn": "value"},
        },
    }


def _make_text_widget(widget_id):
    """Build a text-only widget (no dataSource)."""
    return {
        "id": widget_id,
        "position": {"x": 0, "y": 0, "w": 6, "h": 4},
        "widget": {"type": "text", "config": {"content": "Hello"}},
    }


# ---------------------------------------------------------------------------
# TestCreateDashboardDispatch
# ---------------------------------------------------------------------------

class TestCreateDashboardDispatch:
    """Verify create_dashboard dispatches materialization task after commit."""

    @pytest.mark.asyncio
    async def test_create_dispatches_materialization(self, dashboard_db, test_user):
        from backend.agents.dashboard_tools import build_dashboard_tools

        context = _make_context(test_user.id)
        mock_delay = MagicMock()

        widgets = [_make_widget("w1")]

        with patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", new_callable=AsyncMock, return_value=None), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            mock_task.delay = mock_delay

            tools = build_dashboard_tools(context, lambda: dashboard_db)
            create_fn = tools[0]
            result = await create_fn.ainvoke({
                "title": "Test",
                "description": "Test dashboard",
                "widgets_json": json.dumps(widgets),
            })

        parsed = json.loads(result)
        assert parsed["success"] is True

        # Verify materialization was dispatched
        mock_delay.assert_called_once_with(parsed["dashboard_id"])


# ---------------------------------------------------------------------------
# TestUpdateDashboardDispatch
# ---------------------------------------------------------------------------

class TestUpdateDashboardDispatch:
    """Verify update_dashboard dispatches materialization when SQL changes."""

    def _seed_dashboard(self, db, user_id, widgets):
        d = Dashboard(
            user_id=user_id,
            title="Existing",
            description="",
            widgets=widgets,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(d)
        db.commit()
        db.refresh(d)
        return d

    @pytest.mark.asyncio
    async def test_update_dispatches_on_sql_change(self, dashboard_db, test_user):
        """When widget SQL changes, materialization should be dispatched."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        old_widget = _make_widget("w1", sql="SELECT 1 AS value")
        dashboard = self._seed_dashboard(dashboard_db, test_user.id, [old_widget])

        new_widget = _make_widget("w1", sql="SELECT 2 AS value")
        context = _make_context(test_user.id)
        mock_delay = MagicMock()

        with patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", new_callable=AsyncMock, return_value=None), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            mock_task.delay = mock_delay

            tools = build_dashboard_tools(context, lambda: dashboard_db)
            update_fn = tools[1]
            result = await update_fn.ainvoke({
                "dashboard_id": dashboard.id,
                "widgets": [new_widget],
            })

        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_delay.assert_called_once_with(dashboard.id)

    @pytest.mark.asyncio
    async def test_update_no_dispatch_on_cosmetic_change(self, dashboard_db, test_user):
        """When only title/description changes (SQL unchanged), no materialization."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        widget = _make_widget("w1", sql="SELECT 1 AS value")
        dashboard = self._seed_dashboard(dashboard_db, test_user.id, [widget])

        context = _make_context(test_user.id)
        mock_delay = MagicMock()

        with patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", new_callable=AsyncMock, return_value=None), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            mock_task.delay = mock_delay

            tools = build_dashboard_tools(context, lambda: dashboard_db)
            update_fn = tools[1]
            result = await update_fn.ainvoke({
                "dashboard_id": dashboard.id,
                "widgets": [widget],  # same SQL
                "title": "New Title",
                "description": "New description",
            })

        parsed = json.loads(result)
        assert parsed["success"] is True
        # Materialization should NOT have been dispatched
        mock_delay.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_dispatches_on_connection_change(self, dashboard_db, test_user):
        """When widget connectionId changes (same SQL), materialization should be dispatched."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        old_widget = _make_widget("w1", sql="SELECT 1 AS value", connection_id=1)
        dashboard = self._seed_dashboard(dashboard_db, test_user.id, [old_widget])

        new_widget = _make_widget("w1", sql="SELECT 1 AS value", connection_id=2)
        context = _make_context(test_user.id)
        mock_delay = MagicMock()

        with patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", new_callable=AsyncMock, return_value=None), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            mock_task.delay = mock_delay

            tools = build_dashboard_tools(context, lambda: dashboard_db)
            update_fn = tools[1]
            result = await update_fn.ainvoke({
                "dashboard_id": dashboard.id,
                "widgets": [new_widget],
            })

        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_delay.assert_called_once_with(dashboard.id)


# ---------------------------------------------------------------------------
# TestMaterializeEndpoint
# ---------------------------------------------------------------------------

class TestMaterializeEndpoint:
    """Tests for POST /dashboards/{id}/materialize endpoint."""

    @pytest.mark.asyncio
    async def test_materialize_returns_202(self, dashboard_db, test_user):
        from backend.api.widget_data import materialize_dashboard

        d = Dashboard(
            user_id=test_user.id, title="Test", widgets=[],
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_db.refresh(d)

        mock_task_result = MagicMock()
        mock_task_result.id = "task-abc-123"

        mock_redis = MagicMock()
        mock_redis.exists.return_value = False

        with patch("redis.from_url", return_value=mock_redis), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            mock_task.delay.return_value = mock_task_result

            result = await materialize_dashboard(
                dashboard_id=d.id,
                current_user=test_user,
                db=dashboard_db,
            )

        assert result["task_id"] == "task-abc-123"
        assert "message" in result
        mock_task.delay.assert_called_once_with(d.id)

    @pytest.mark.asyncio
    async def test_materialize_rate_limit(self, dashboard_db, test_user):
        from backend.api.widget_data import materialize_dashboard
        from fastapi import HTTPException

        d = Dashboard(
            user_id=test_user.id, title="Test", widgets=[],
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_db.refresh(d)

        mock_redis = MagicMock()
        mock_redis.exists.return_value = True  # Rate limit key exists

        with patch("redis.from_url", return_value=mock_redis):
            with pytest.raises(HTTPException) as exc_info:
                await materialize_dashboard(
                    dashboard_id=d.id,
                    current_user=test_user,
                    db=dashboard_db,
                )

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_materialize_checks_ownership(self, dashboard_db, test_user):
        from backend.api.widget_data import materialize_dashboard
        from fastapi import HTTPException

        # Dashboard belongs to a different user
        d = Dashboard(
            user_id="other-user", title="Not Mine", widgets=[],
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_db.refresh(d)

        with pytest.raises(HTTPException) as exc_info:
            await materialize_dashboard(
                dashboard_id=d.id,
                current_user=test_user,
                db=dashboard_db,
            )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# TestInlineExecutionAlongsideAsync
# ---------------------------------------------------------------------------

class TestInlineExecutionAlongsideAsync:
    """Verify _execute_widget_sql still runs inline alongside async materialization."""

    @pytest.mark.asyncio
    async def test_inline_sql_runs_before_dispatch(self, dashboard_db, test_user):
        """create_dashboard should execute SQL inline AND dispatch async materialization."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        context = _make_context(test_user.id)

        execute_calls = []

        async def mock_execute(widget, db_factory, data_context=None, user_id=None):
            execute_calls.append(widget["id"])
            widget["widget"]["config"]["value"] = 42
            return None

        mock_delay = MagicMock()

        widgets = [_make_widget("w1")]

        with patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", side_effect=mock_execute), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task:
            mock_task.delay = mock_delay

            tools = build_dashboard_tools(context, lambda: dashboard_db)
            create_fn = tools[0]
            result = await create_fn.ainvoke({
                "title": "Test",
                "description": "Test",
                "widgets_json": json.dumps(widgets),
            })

        parsed = json.loads(result)
        assert parsed["success"] is True

        # Inline execution happened
        assert "w1" in execute_calls

        # Async materialization also dispatched
        mock_delay.assert_called_once()

        # Widget config was populated by inline execution
        d = dashboard_db.query(Dashboard).filter(Dashboard.id == parsed["dashboard_id"]).first()
        assert d.widgets[0]["widget"]["config"]["value"] == 42
