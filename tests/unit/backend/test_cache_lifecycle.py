"""Unit tests for Phase 6 — Cache Lifecycle Management.

Tests cover:
- Daily dispatch triggers materialization with staggered delays
- API responses include cache_built_at and cache_status
- Dashboard delete removes SQLite from DO Spaces and local cache
- Connection modification marks dependent dashboard caches as 'stale'
- Connection deletion marks dependent dashboard caches as 'stale'
- Stale cache triggers fallback to source DB on next read
- Stale cache is rebuilt on next scheduled refresh
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
def lifecycle_db():
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
def test_user(lifecycle_db):
    user = User(id="user-1", email="test@example.com", auth_provider="sso")
    lifecycle_db.add(user)
    lifecycle_db.commit()
    return user


def _make_dashboard(db, user_id, title="Test", widgets=None, cache_status=None,
                    cache_key=None, cache_built_at=None, schedule_active=False,
                    cron_expression=None, next_run_at=None):
    d = Dashboard(
        user_id=user_id,
        title=title,
        widgets=widgets or [],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        cache_status=cache_status,
        cache_key=cache_key,
        cache_built_at=cache_built_at,
        schedule_active=schedule_active,
        cron_expression=cron_expression,
        next_run_at=next_run_at,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _make_widget(widget_id, sql="SELECT 1", connection_id=1):
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


# ---------------------------------------------------------------------------
# TestDailyDispatchStagger
# ---------------------------------------------------------------------------

class TestDailyDispatchStagger:
    """Verify dispatch_dashboard_refreshes staggers tasks with random delays."""

    def test_dispatch_triggers_materialization(self, lifecycle_db, test_user):
        """Due dashboards should have materialization dispatched."""
        import sys
        # Mock croniter module if not installed
        mock_croniter_mod = MagicMock()
        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = datetime(2030, 1, 1)
        mock_croniter_mod.croniter.return_value = mock_croniter_instance
        sys.modules["croniter"] = mock_croniter_mod

        from backend.tasks.dashboard_refresh_tasks import dispatch_dashboard_refreshes

        d1 = _make_dashboard(
            lifecycle_db, test_user.id,
            schedule_active=True,
            cron_expression="*/15 * * * *",
            next_run_at=datetime(2020, 1, 1),  # past = due
        )
        d2 = _make_dashboard(
            lifecycle_db, test_user.id,
            schedule_active=True,
            cron_expression="0 * * * *",
            next_run_at=datetime(2020, 1, 1),
        )

        mock_apply = MagicMock()

        with patch("backend.tasks.dashboard_refresh_tasks.SessionLocal", return_value=lifecycle_db), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task, \
             patch("backend.tasks.dashboard_refresh_tasks.random") as mock_random:
            mock_task.apply_async = mock_apply
            mock_random.uniform.return_value = 5.0

            dispatch_dashboard_refreshes()

        # Both dashboards should have been dispatched
        assert mock_apply.call_count == 2

    def test_dispatch_uses_staggered_countdown(self, lifecycle_db, test_user):
        """Each dashboard dispatch should use apply_async with countdown."""
        import sys
        mock_croniter_mod = MagicMock()
        mock_croniter_instance = MagicMock()
        mock_croniter_instance.get_next.return_value = datetime(2030, 1, 1)
        mock_croniter_mod.croniter.return_value = mock_croniter_instance
        sys.modules["croniter"] = mock_croniter_mod

        from backend.tasks.dashboard_refresh_tasks import dispatch_dashboard_refreshes, STAGGER_MAX_SECONDS

        d = _make_dashboard(
            lifecycle_db, test_user.id,
            schedule_active=True,
            cron_expression="*/15 * * * *",
            next_run_at=datetime(2020, 1, 1),
        )
        dashboard_id = d.id

        mock_apply = MagicMock()

        with patch("backend.tasks.dashboard_refresh_tasks.SessionLocal", return_value=lifecycle_db), \
             patch("backend.tasks.dashboard_refresh_tasks.execute_dashboard_refresh") as mock_task, \
             patch("backend.tasks.dashboard_refresh_tasks.random") as mock_random:
            mock_task.apply_async = mock_apply
            mock_random.uniform.return_value = 15.5

            dispatch_dashboard_refreshes()

        # Verify apply_async was called with countdown parameter
        mock_apply.assert_called_once()
        call_kwargs = mock_apply.call_args
        # countdown = random.uniform(0, STAGGER_MAX_SECONDS) + idx * 2 = 15.5 + 0 = 15.5
        assert call_kwargs == call(args=[dashboard_id], countdown=15.5)
        # Verify random.uniform was called with (0, STAGGER_MAX_SECONDS)
        mock_random.uniform.assert_called_with(0, STAGGER_MAX_SECONDS)


# ---------------------------------------------------------------------------
# TestCacheStatusInApiResponse
# ---------------------------------------------------------------------------

class TestCacheStatusInApiResponse:
    """Verify API responses include cache_built_at and cache_status."""

    def test_widget_refresh_response_includes_cache_fields(self):
        from backend.schemas.widget_data import WidgetRefreshResponse

        resp = WidgetRefreshResponse(
            config={"value": 42},
            execution_time_ms=10.0,
            row_count=1,
            refreshed_at="2026-01-01T00:00:00",
            cache_built_at="2026-01-01T00:00:00",
            cache_status="ready",
        )
        assert resp.cache_built_at == "2026-01-01T00:00:00"
        assert resp.cache_status == "ready"

    def test_widget_refresh_response_cache_fields_optional(self):
        from backend.schemas.widget_data import WidgetRefreshResponse

        resp = WidgetRefreshResponse(
            config={"value": 42},
            execution_time_ms=10.0,
            row_count=1,
            refreshed_at="2026-01-01T00:00:00",
        )
        assert resp.cache_built_at is None
        assert resp.cache_status is None

    def test_bulk_refresh_response_includes_cache_fields(self):
        from backend.schemas.widget_data import BulkRefreshResponse

        resp = BulkRefreshResponse(
            widgets={"w1": {"config": {}}},
            cache_built_at="2026-01-01T00:00:00",
            cache_status="ready",
        )
        assert resp.cache_built_at == "2026-01-01T00:00:00"
        assert resp.cache_status == "ready"

    def test_dashboard_response_includes_cache_fields(self):
        from backend.api.dashboards import DashboardResponse

        resp = DashboardResponse(
            id=1,
            title="Test",
            description=None,
            widgets=[],
            created_at="2026-01-01",
            updated_at="2026-01-01",
            cache_built_at="2026-01-01T00:00:00",
            cache_status="ready",
        )
        assert resp.cache_built_at == "2026-01-01T00:00:00"
        assert resp.cache_status == "ready"


# ---------------------------------------------------------------------------
# TestDashboardDeleteCacheCleanup
# ---------------------------------------------------------------------------

class TestDashboardDeleteCacheCleanup:
    """Verify dashboard delete removes SQLite from DO Spaces and local cache."""

    @pytest.mark.asyncio
    async def test_delete_calls_delete_cache(self, lifecycle_db, test_user):
        """Deleting a dashboard with a cache should call delete_cache."""
        from backend.api.dashboards import delete_dashboard

        d = _make_dashboard(
            lifecycle_db, test_user.id,
            cache_key="some/path/1.sqlite",
            cache_status="ready",
        )
        dashboard_id = d.id

        with patch("backend.services.dashboard_cache.delete_cache") as mock_delete_cache:
            await delete_dashboard(
                dashboard_id=dashboard_id,
                db=lifecycle_db,
                current_user=test_user,
            )

        mock_delete_cache.assert_called_once_with(dashboard_id)
        assert lifecycle_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first() is None

    @pytest.mark.asyncio
    async def test_delete_without_cache_skips_cleanup(self, lifecycle_db, test_user):
        """Deleting a dashboard without cache should not call delete_cache."""
        from backend.api.dashboards import delete_dashboard

        d = _make_dashboard(lifecycle_db, test_user.id)
        dashboard_id = d.id

        with patch("backend.services.dashboard_cache.delete_cache") as mock_delete_cache:
            await delete_dashboard(
                dashboard_id=dashboard_id,
                db=lifecycle_db,
                current_user=test_user,
            )

        mock_delete_cache.assert_not_called()
        assert lifecycle_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first() is None

    @pytest.mark.asyncio
    async def test_delete_cache_failure_does_not_block_delete(self, lifecycle_db, test_user):
        """Cache cleanup failure should not prevent dashboard deletion."""
        from backend.api.dashboards import delete_dashboard

        d = _make_dashboard(
            lifecycle_db, test_user.id,
            cache_key="some/path/1.sqlite",
            cache_status="ready",
        )
        dashboard_id = d.id

        with patch("backend.services.dashboard_cache.delete_cache", side_effect=Exception("DO Spaces down")):
            await delete_dashboard(
                dashboard_id=dashboard_id,
                db=lifecycle_db,
                current_user=test_user,
            )

        # Dashboard should still be deleted despite cache cleanup failure
        assert lifecycle_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first() is None


# ---------------------------------------------------------------------------
# TestConnectionChangeInvalidation
# ---------------------------------------------------------------------------

class TestConnectionChangeInvalidation:
    """Verify connection modification/deletion marks dependent caches as 'stale'."""

    def test_connection_update_marks_dependent_caches_stale(self, lifecycle_db, test_user):
        from backend.api.connections import _invalidate_dashboard_caches_for_connection

        widget = _make_widget("w1", connection_id=5)
        d = _make_dashboard(
            lifecycle_db, test_user.id,
            widgets=[widget],
            cache_status="ready",
            cache_key="path/5.sqlite",
        )

        count = _invalidate_dashboard_caches_for_connection(5, test_user.id, lifecycle_db)
        lifecycle_db.commit()

        lifecycle_db.refresh(d)
        assert d.cache_status == "stale"
        assert count == 1

    def test_connection_delete_marks_dependent_caches_stale(self, lifecycle_db, test_user):
        from backend.api.connections import _invalidate_dashboard_caches_for_connection

        widget = _make_widget("w1", connection_id=7)
        d = _make_dashboard(
            lifecycle_db, test_user.id,
            widgets=[widget],
            cache_status="ready",
            cache_key="path/7.sqlite",
        )

        count = _invalidate_dashboard_caches_for_connection(7, test_user.id, lifecycle_db)
        lifecycle_db.commit()

        lifecycle_db.refresh(d)
        assert d.cache_status == "stale"
        assert count == 1

    def test_unrelated_dashboard_not_affected(self, lifecycle_db, test_user):
        """Dashboard using a different connection should not be marked stale."""
        from backend.api.connections import _invalidate_dashboard_caches_for_connection

        widget = _make_widget("w1", connection_id=10)
        d = _make_dashboard(
            lifecycle_db, test_user.id,
            widgets=[widget],
            cache_status="ready",
            cache_key="path/10.sqlite",
        )

        # Invalidate connection 99 — dashboard uses connection 10
        count = _invalidate_dashboard_caches_for_connection(99, test_user.id, lifecycle_db)
        lifecycle_db.commit()

        lifecycle_db.refresh(d)
        assert d.cache_status == "ready"
        assert count == 0

    def test_multiple_dashboards_marked_stale(self, lifecycle_db, test_user):
        """All dashboards using the modified connection should be marked stale."""
        from backend.api.connections import _invalidate_dashboard_caches_for_connection

        w1 = _make_widget("w1", connection_id=3)
        w2 = _make_widget("w2", connection_id=3)
        d1 = _make_dashboard(
            lifecycle_db, test_user.id,
            widgets=[w1],
            cache_status="ready",
            cache_key="path/a.sqlite",
        )
        d2 = _make_dashboard(
            lifecycle_db, test_user.id,
            widgets=[w2],
            cache_status="ready",
            cache_key="path/b.sqlite",
        )

        count = _invalidate_dashboard_caches_for_connection(3, test_user.id, lifecycle_db)
        lifecycle_db.commit()

        lifecycle_db.refresh(d1)
        lifecycle_db.refresh(d2)
        assert d1.cache_status == "stale"
        assert d2.cache_status == "stale"
        assert count == 2

    def test_already_stale_or_no_cache_not_affected(self, lifecycle_db, test_user):
        """Dashboards without cache or already stale should not be touched."""
        from backend.api.connections import _invalidate_dashboard_caches_for_connection

        w = _make_widget("w1", connection_id=3)
        # No cache_status
        d1 = _make_dashboard(lifecycle_db, test_user.id, widgets=[w])
        # Already stale
        d2 = _make_dashboard(
            lifecycle_db, test_user.id, widgets=[w],
            cache_status="stale",
        )

        count = _invalidate_dashboard_caches_for_connection(3, test_user.id, lifecycle_db)
        lifecycle_db.commit()

        lifecycle_db.refresh(d1)
        lifecycle_db.refresh(d2)
        assert d1.cache_status is None
        assert d2.cache_status == "stale"
        assert count == 0


# ---------------------------------------------------------------------------
# TestStaleCacheFallback
# ---------------------------------------------------------------------------

class TestStaleCacheFallback:
    """Verify stale cache triggers fallback to source DB on next read."""

    @pytest.mark.asyncio
    async def test_stale_cache_falls_back_to_source_db(self, lifecycle_db, test_user):
        """When cache_status is 'stale', refresh_widget should use source DB, not cache."""
        from backend.api.widget_data import refresh_widget
        from backend.schemas.widget_data import WidgetRefreshRequest
        from backend.connectors.base import QueryResult

        d = _make_dashboard(
            lifecycle_db, test_user.id,
            widgets=[_make_widget("w1")],
            cache_status="stale",
            cache_key="old/key.sqlite",
        )

        request = WidgetRefreshRequest(
            connection_id=1,
            sql="SELECT 1 AS value",
            mapping={"type": "kpi", "valueColumn": "value"},
            dashboard_id=d.id,
            widget_id="w1",
        )

        mock_conn = MagicMock()
        mock_result = QueryResult(
            columns=["value"], rows=[(42,)], row_count=1, execution_time_ms=5.0,
        )
        mock_conn.execute_query.return_value = mock_result

        mock_db_connection = MagicMock()
        mock_db_connection.id = 1
        mock_db_connection.user_id = test_user.id

        with patch("backend.api.widget_data.get_db", return_value=lifecycle_db), \
             patch.object(lifecycle_db, 'query') as mock_query:

            # First query returns Dashboard, second returns DatabaseConnection
            dashboard_filter = MagicMock()
            dashboard_filter.first.return_value = d
            conn_filter = MagicMock()
            conn_filter.first.return_value = mock_db_connection
            mock_query.return_value.filter.side_effect = [dashboard_filter, conn_filter]

            with patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_conn):
                result = await refresh_widget(
                    request=request,
                    current_user=test_user,
                    db=lifecycle_db,
                )

        # Should have used source DB (connector.execute_query was called)
        mock_conn.execute_query.assert_called_once()
        assert result.cache_status == "stale"


# ---------------------------------------------------------------------------
# TestStaleRebuildOnScheduledRefresh
# ---------------------------------------------------------------------------

class TestStaleRebuildOnScheduledRefresh:
    """Verify stale cache is rebuilt on next scheduled refresh."""

    def test_scheduled_refresh_rebuilds_stale_cache(self, lifecycle_db, test_user):
        """execute_dashboard_refresh should rebuild a stale cache via materialize_dashboard."""
        from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh

        d = _make_dashboard(
            lifecycle_db, test_user.id,
            cache_status="stale",
            cache_key="old/key.sqlite",
        )
        dashboard_id = d.id  # capture before session replacement

        mock_result = MagicMock()
        mock_result.widgets_total = 1
        mock_result.widgets_succeeded = 1
        mock_result.widgets_failed = 0
        mock_result.widget_errors = None

        with patch("backend.tasks.dashboard_refresh_tasks.SessionLocal", return_value=lifecycle_db), \
             patch("backend.services.dashboard_cache.materialize_dashboard", return_value=mock_result) as mock_mat:

            execute_dashboard_refresh(dashboard_id)

        mock_mat.assert_called_once_with(dashboard_id)
        # Run should have been recorded
        runs = lifecycle_db.query(DashboardRefreshRun).filter(
            DashboardRefreshRun.dashboard_id == dashboard_id,
        ).all()
        assert len(runs) == 1
        assert runs[0].status == "completed"
