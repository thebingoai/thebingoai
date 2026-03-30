"""Tests for Phase 2: dashboard refresh task with SQLite materialization.

Tests cover:
- Celery task delegates to materialize_dashboard and records run
- Connection sharing (one connector per connectionId)
- Error isolation (partial success = 'ready', all fail = 'failed')
- Date range filtering (trendDateColumn, data_context, no date column)
- cache_built_at updated after success
- Empty query results handled gracefully
"""

import os
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from backend.connectors.base import QueryResult
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun
from backend.services.dashboard_cache import (
    MaterializeResult,
    _apply_date_filter,
    _get_date_column,
    _sanitize_widget_id,
    materialize_dashboard,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_widget(widget_id, connection_id, sql, mapping=None):
    """Helper to create a widget dict."""
    w = {
        "id": widget_id,
        "dataSource": {
            "connectionId": connection_id,
            "sql": sql,
        },
        "widget": {"type": "chart", "config": {}},
    }
    if mapping:
        w["dataSource"]["mapping"] = mapping
    return w


def _patch_db_connection(dashboard_db):
    """Patch dashboard_db.query to return a mock for DatabaseConnection lookups."""
    from backend.models.database_connection import DatabaseConnection

    mock_connection = MagicMock()
    mock_connection.db_type = "postgres"

    orig_query = dashboard_db.query

    def patched_query(model):
        q = orig_query(model)
        if model is DatabaseConnection:
            mock_q = MagicMock()
            mock_filter = MagicMock()
            mock_filter.first.return_value = mock_connection
            mock_q.filter.return_value = mock_filter
            return mock_q
        return q

    dashboard_db.query = patched_query
    return mock_connection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache_dir(tmp_path):
    """Override CACHE_DIR to use a temp directory for test isolation."""
    cache = tmp_path / "dashboard_cache"
    cache.mkdir()
    with patch("backend.services.dashboard_cache.CACHE_DIR", str(cache)):
        yield str(cache)


# ---------------------------------------------------------------------------
# Unit Tests: _get_date_column / _apply_date_filter
# ---------------------------------------------------------------------------

class TestGetDateColumn:

    def test_from_mapping_trend_date_column(self):
        widget = {"dataSource": {"mapping": {"trendDateColumn": "order_date"}}}
        assert _get_date_column(widget, None) == "order_date"

    def test_from_data_context(self):
        widget = {"dataSource": {"mapping": {}}}
        ctx = {"dimensions": {"d": {"column": "created_at", "type": "date"}}}
        assert _get_date_column(widget, ctx) == "created_at"

    def test_mapping_takes_priority_over_context(self):
        widget = {"dataSource": {"mapping": {"trendDateColumn": "order_date"}}}
        ctx = {"dimensions": {"d": {"column": "created_at", "type": "date"}}}
        assert _get_date_column(widget, ctx) == "order_date"

    def test_returns_none_when_no_date(self):
        widget = {"dataSource": {"mapping": {}}}
        assert _get_date_column(widget, None) is None

    def test_returns_none_for_non_date_dimensions(self):
        widget = {"dataSource": {"mapping": {}}}
        ctx = {"dimensions": {"region": {"column": "region", "type": "string"}}}
        assert _get_date_column(widget, ctx) is None


class TestApplyDateFilter:

    def test_wraps_sql_with_date_filter(self):
        result = _apply_date_filter("SELECT * FROM orders", "order_date", 30)
        assert result.startswith('SELECT * FROM (SELECT * FROM orders)')
        assert '"order_date"' in result
        assert "_date_scoped" in result

    def test_cutoff_date_correct(self):
        result = _apply_date_filter("SELECT 1", "d", 90)
        cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
        assert cutoff in result


# ---------------------------------------------------------------------------
# Celery Task Tests
# ---------------------------------------------------------------------------

class TestExecuteDashboardRefresh:
    """Test the Celery task delegates to materialize_dashboard."""

    def test_creates_run_and_records_result(self, dashboard_db, test_user):
        """Task creates a DashboardRefreshRun and records materialize result."""
        d = Dashboard(user_id=test_user.id, title="Test", widgets=[])
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_id = d.id

        mock_result = MaterializeResult(
            do_key="bingo/dev/user-1/dashboards/1.sqlite",
            widgets_total=3,
            widgets_succeeded=2,
            widgets_failed=1,
            widget_errors={"bad-widget": "query failed"},
        )

        with patch("backend.tasks.dashboard_refresh_tasks.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.dashboard_cache.materialize_dashboard", return_value=mock_result) as mock_mat:

            from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
            execute_dashboard_refresh(dashboard_id)

            mock_mat.assert_called_once_with(dashboard_id)

        runs = dashboard_db.query(DashboardRefreshRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "completed"
        assert run.widgets_total == 3
        assert run.widgets_succeeded == 2
        assert run.widgets_failed == 1
        assert run.widget_errors == {"bad-widget": "query failed"}
        assert run.completed_at is not None
        assert run.duration_ms is not None

    def test_failed_materialization_marks_run_failed(self, dashboard_db, test_user):
        """If materialize_dashboard raises, the run is marked 'failed'."""
        d = Dashboard(user_id=test_user.id, title="Test", widgets=[])
        dashboard_db.add(d)
        dashboard_db.commit()
        dashboard_id = d.id

        with patch("backend.tasks.dashboard_refresh_tasks.SessionLocal", return_value=dashboard_db), \
             patch("backend.services.dashboard_cache.materialize_dashboard", side_effect=RuntimeError("boom")):

            from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
            execute_dashboard_refresh(dashboard_id)

        runs = dashboard_db.query(DashboardRefreshRun).all()
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert "boom" in runs[0].error


# ---------------------------------------------------------------------------
# Connection Sharing Tests
# ---------------------------------------------------------------------------

class TestConnectionSharing:
    """Widgets sharing a connectionId should use a single connector."""

    def test_same_connection_id_uses_one_connector(self, dashboard_db, test_user, cache_dir):
        """Two widgets with the same connectionId -> get_connector_for_connection called once."""
        dashboard = Dashboard(
            user_id=test_user.id,
            title="Shared Connection",
            widgets=[
                _make_widget("w1", 1, "SELECT 1 AS a"),
                _make_widget("w2", 1, "SELECT 2 AS b"),
            ],
        )
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        mock_connector = MagicMock()
        mock_connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[(1,)], row_count=1, execution_time_ms=10,
        )

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector) as mock_get_conn, \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            result = materialize_dashboard(dashboard_id)

        # get_connector_for_connection called once for the shared connection
        assert mock_get_conn.call_count == 1
        # execute_query called twice (once per widget)
        assert mock_connector.execute_query.call_count == 2
        assert result.widgets_total == 2
        assert result.widgets_succeeded == 2


# ---------------------------------------------------------------------------
# Error Isolation Tests
# ---------------------------------------------------------------------------

class TestErrorIsolation:
    """Individual widget failures should not prevent other widgets from being materialized."""

    def test_one_fails_others_succeed_status_ready(self, dashboard_db, test_user, cache_dir):
        """If one widget fails but others succeed, cache_status = 'ready'."""
        dashboard = Dashboard(
            user_id=test_user.id,
            title="Partial Failure",
            widgets=[
                _make_widget("good1", 1, "SELECT 1 AS x"),
                _make_widget("bad", 1, "SELECT fail"),
                _make_widget("good2", 1, "SELECT 2 AS y"),
            ],
        )
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        def mock_execute(sql):
            if "fail" in sql:
                raise RuntimeError("Query failed")
            return QueryResult(columns=["x"], rows=[(1,)], row_count=1, execution_time_ms=10)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = mock_execute

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            result = materialize_dashboard(dashboard_id)

        assert result.widgets_succeeded == 2
        assert result.widgets_failed == 1
        assert "bad" in result.widget_errors

        d = dashboard_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        assert d.cache_status == "ready"

    def test_all_fail_status_failed(self, dashboard_db, test_user, cache_dir):
        """If ALL widgets fail, cache_status = 'failed'."""
        dashboard = Dashboard(
            user_id=test_user.id,
            title="Total Failure",
            widgets=[
                _make_widget("w1", 1, "SELECT fail1"),
                _make_widget("w2", 1, "SELECT fail2"),
            ],
        )
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = RuntimeError("All queries fail")

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            result = materialize_dashboard(dashboard_id)

        assert result.widgets_succeeded == 0
        assert result.widgets_failed == 2

        d = dashboard_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        assert d.cache_status == "failed"


# ---------------------------------------------------------------------------
# Date Range Filtering Tests
# ---------------------------------------------------------------------------

class TestDateRangeFiltering:

    def test_date_filter_with_trend_date_column(self, dashboard_db, test_user, cache_dir):
        """Date filter is applied when widget mapping has trendDateColumn."""
        dashboard = Dashboard(
            user_id=test_user.id,
            title="Date Filtered",
            widgets=[
                _make_widget("w1", 1, "SELECT * FROM orders", mapping={"trendDateColumn": "order_date"}),
            ],
            cache_date_range_days=30,
        )
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        captured_sql = []

        def capture_execute(sql):
            captured_sql.append(sql)
            return QueryResult(columns=["x"], rows=[(1,)], row_count=1, execution_time_ms=10)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = capture_execute

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            materialize_dashboard(dashboard_id)

        assert len(captured_sql) == 1
        assert '"order_date"' in captured_sql[0]
        assert "_date_scoped" in captured_sql[0]

    def test_no_date_filter_without_date_column(self, dashboard_db, test_user, cache_dir):
        """No date filter when widget has no trendDateColumn and no data_context."""
        original_sql = "SELECT * FROM orders"
        dashboard = Dashboard(
            user_id=test_user.id,
            title="No Date",
            widgets=[_make_widget("w1", 1, original_sql)],
        )
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        captured_sql = []

        def capture_execute(sql):
            captured_sql.append(sql)
            return QueryResult(columns=["x"], rows=[(1,)], row_count=1, execution_time_ms=10)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = capture_execute

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            materialize_dashboard(dashboard_id)

        assert len(captured_sql) == 1
        assert captured_sql[0] == original_sql  # No wrapping

    def test_data_context_date_dimension_used(self, dashboard_db, test_user, cache_dir):
        """Date filter uses data_context dimensions when no trendDateColumn."""
        dashboard = Dashboard(
            user_id=test_user.id,
            title="Context Date",
            widgets=[_make_widget("w1", 1, "SELECT * FROM orders")],
            data_context={
                "dimensions": {
                    "order_date": {"column": "order_date", "type": "date", "sources": ["orders"]},
                },
            },
            cache_date_range_days=60,
        )
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        captured_sql = []

        def capture_execute(sql):
            captured_sql.append(sql)
            return QueryResult(columns=["x"], rows=[(1,)], row_count=1, execution_time_ms=10)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = capture_execute

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            materialize_dashboard(dashboard_id)

        assert len(captured_sql) == 1
        assert '"order_date"' in captured_sql[0]
        assert "_date_scoped" in captured_sql[0]


# ---------------------------------------------------------------------------
# Cache Built At Tests
# ---------------------------------------------------------------------------

class TestCacheBuiltAt:

    def test_cache_built_at_updated(self, dashboard_db, test_user, cache_dir):
        """cache_built_at is set after successful materialization."""
        dashboard = Dashboard(user_id=test_user.id, title="Test", widgets=[
            _make_widget("w1", 1, "SELECT 1 AS a"),
        ])
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        mock_connector = MagicMock()
        mock_connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[(1,)], row_count=1, execution_time_ms=10,
        )

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            materialize_dashboard(dashboard_id)

        d = dashboard_db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
        assert d.cache_built_at is not None
        assert isinstance(d.cache_built_at, datetime)


# ---------------------------------------------------------------------------
# Empty Results Tests
# ---------------------------------------------------------------------------

class TestEmptyResults:

    def test_handles_empty_query_results(self, dashboard_db, test_user, cache_dir):
        """Widgets with 0 rows create the table and record row_count=0."""
        dashboard = Dashboard(user_id=test_user.id, title="Empty", widgets=[
            _make_widget("w1", 1, "SELECT 1 AS a WHERE 1=0"),
        ])
        dashboard_db.add(dashboard)
        dashboard_db.commit()
        dashboard_id = dashboard.id

        _patch_db_connection(dashboard_db)

        mock_connector = MagicMock()
        mock_connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[], row_count=0, execution_time_ms=5,
        )

        with patch("backend.database.session.SessionLocal", return_value=dashboard_db), \
             patch("backend.connectors.factory.get_connector_for_connection", return_value=mock_connector), \
             patch("backend.connectors.factory.get_connector_registration", return_value=None), \
             patch("backend.services.object_storage.upload_bytes"), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.do_spaces_base_path = "bingo/test"
            result = materialize_dashboard(dashboard_id)

        assert result.widgets_succeeded == 1
        assert result.widgets_failed == 0

        # Verify the SQLite file has the table with 0 rows
        cache_path = os.path.join(cache_dir, f"{dashboard_id}.sqlite")
        conn = sqlite3.connect(cache_path)
        try:
            rows = conn.execute('SELECT * FROM "w1"').fetchall()
            assert rows == []
            meta = conn.execute("SELECT row_count FROM _meta WHERE widget_id='w1'").fetchone()
            assert meta[0] == 0
        finally:
            conn.close()
