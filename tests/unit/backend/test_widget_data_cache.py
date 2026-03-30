"""Unit tests for Phase 3 — Cache-aware widget refresh endpoints.

Tests the SQLite cache read path in widget_data.py:
- inject_filters_sqlite (filter injection for flat SQLite tables)
- _read_widget_from_cache (cache reader returning QueryResult)
- refresh_widget cache path + fallback
- refresh_dashboard_widgets cache path + fallback
- Transform compatibility (SQLite vs source DB QueryResult)
"""

import os
import sqlite3
import tempfile

import pytest
from unittest.mock import MagicMock, patch

from backend.api.widget_data import (
    inject_filters_sqlite,
    _read_widget_from_cache,
    refresh_widget,
    refresh_dashboard_widgets,
)
from backend.schemas.widget_data import FilterParam, WidgetRefreshRequest
from backend.connectors.base import QueryResult
from backend.services.dashboard_cache import _sanitize_widget_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cache_dir():
    """Temp directory for SQLite cache files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_cache(cache_dir):
    """Create a sample SQLite cache with two widget tables + _meta."""
    cache_path = os.path.join(cache_dir, "1.sqlite")
    conn = sqlite3.connect(cache_path)

    conn.execute(
        "CREATE TABLE _meta ("
        "  widget_id TEXT PRIMARY KEY,"
        "  table_name TEXT NOT NULL,"
        "  original_sql TEXT,"
        "  materialized_at TEXT NOT NULL,"
        "  row_count INTEGER NOT NULL DEFAULT 0,"
        "  error TEXT"
        ")"
    )

    # Widget 1: kpi-revenue → kpi_revenue
    conn.execute('CREATE TABLE "kpi_revenue" (region TEXT, amount REAL, order_date TEXT)')
    conn.executemany(
        'INSERT INTO "kpi_revenue" VALUES (?, ?, ?)',
        [
            ("North", 100.0, "2024-01-15"),
            ("South", 200.0, "2024-02-20"),
            ("North", 150.0, "2024-03-10"),
        ],
    )
    conn.execute(
        "INSERT INTO _meta VALUES (?, ?, ?, ?, ?, NULL)",
        ("kpi-revenue", "kpi_revenue", "SELECT region, amount, order_date FROM orders",
         "2024-01-01T00:00:00", 3),
    )

    # Widget 2: chart-monthly → chart_monthly
    conn.execute('CREATE TABLE "chart_monthly" (month TEXT, total REAL)')
    conn.executemany(
        'INSERT INTO "chart_monthly" VALUES (?, ?)',
        [("Jan", 300.0), ("Feb", 450.0)],
    )
    conn.execute(
        "INSERT INTO _meta VALUES (?, ?, ?, ?, ?, NULL)",
        ("chart-monthly", "chart_monthly", "SELECT month, total FROM monthly_summary",
         "2024-01-01T00:00:00", 2),
    )

    conn.commit()
    conn.close()
    return cache_path


# Patch targets (lazy imports in function bodies → patch at source module)
_PATCH_GET_CACHE_PATH = "backend.services.dashboard_cache.get_cache_path"
_PATCH_CONNECTOR_FACTORY = "backend.connectors.factory.get_connector_for_connection"


# ---------------------------------------------------------------------------
# inject_filters_sqlite
# ---------------------------------------------------------------------------

class TestInjectFiltersSqlite:

    def test_no_filters_returns_select_star(self):
        sql, params = inject_filters_sqlite("kpi_revenue", [])
        assert sql == 'SELECT * FROM "kpi_revenue"'
        assert params == []

    def test_single_eq_filter(self):
        filters = [FilterParam(column="region", op="eq", value="North")]
        sql, params = inject_filters_sqlite("kpi_revenue", filters)
        assert sql == 'SELECT * FROM "kpi_revenue" WHERE "region" = ?'
        assert params == ["North"]

    def test_multiple_filters_and(self):
        filters = [
            FilterParam(column="region", op="eq", value="North"),
            FilterParam(column="amount", op="gte", value=100),
        ]
        sql, params = inject_filters_sqlite("kpi_revenue", filters)
        assert sql == 'SELECT * FROM "kpi_revenue" WHERE "region" = ? AND "amount" >= ?'
        assert params == ["North", 100]

    def test_in_filter(self):
        filters = [FilterParam(column="region", op="in", value=["North", "South"])]
        sql, params = inject_filters_sqlite("kpi_revenue", filters)
        assert sql == 'SELECT * FROM "kpi_revenue" WHERE "region" IN (?, ?)'
        assert params == ["North", "South"]

    def test_ilike_becomes_like(self):
        filters = [FilterParam(column="region", op="ilike", value="%north%")]
        sql, params = inject_filters_sqlite("kpi_revenue", filters)
        assert sql == 'SELECT * FROM "kpi_revenue" WHERE "region" LIKE ?'
        assert params == ["%north%"]

    def test_dimension_aware_excludes_inapplicable(self):
        """Filters for dimensions not applicable to widget sources are excluded."""
        data_context = {
            "dimensions": {
                "region": {"column": "region", "sources": ["orders"]},
                "payment_date": {"column": "payment_date", "sources": ["payments"]},
            }
        }
        filters = [
            FilterParam(column="region", op="eq", value="North"),
            FilterParam(column="payment_date", op="gte", value="2024-01-01"),
        ]
        sql, params = inject_filters_sqlite(
            "kpi_revenue", filters,
            data_context=data_context,
            widget_sources=["orders"],
        )
        # Only region filter applied (payment_date not in orders sources)
        assert sql == 'SELECT * FROM "kpi_revenue" WHERE "region" = ?'
        assert params == ["North"]

    def test_sanitized_table_prevents_injection(self):
        """_sanitize_widget_id strips special chars; FilterParam validates column names."""
        bad_name = 'widget"; DROP TABLE users; --'
        safe_name = _sanitize_widget_id(bad_name)
        filters = [FilterParam(column="col", op="eq", value="val")]
        sql, params = inject_filters_sqlite(safe_name, filters)
        assert "DROP" not in sql
        assert params == ["val"]


# ---------------------------------------------------------------------------
# _read_widget_from_cache
# ---------------------------------------------------------------------------

class TestReadWidgetFromCache:

    def test_returns_query_result(self, sample_cache):
        with patch(_PATCH_GET_CACHE_PATH, return_value=sample_cache):
            result = _read_widget_from_cache(1, "kpi-revenue")
        assert isinstance(result, QueryResult)
        assert result.columns == ["region", "amount", "order_date"]
        assert result.row_count == 3
        assert ("North", 100.0, "2024-01-15") in result.rows

    def test_applies_filters(self, sample_cache):
        filters = [FilterParam(column="region", op="eq", value="North")]
        with patch(_PATCH_GET_CACHE_PATH, return_value=sample_cache):
            result = _read_widget_from_cache(1, "kpi-revenue", filters=filters)
        assert result.row_count == 2
        assert all(row[0] == "North" for row in result.rows)

    def test_missing_widget_raises_valueerror(self, sample_cache):
        with patch(_PATCH_GET_CACHE_PATH, return_value=sample_cache):
            with pytest.raises(ValueError, match="not found in cache"):
                _read_widget_from_cache(1, "nonexistent-widget")

    def test_missing_cache_raises_filenotfounderror(self):
        with patch(_PATCH_GET_CACHE_PATH, side_effect=FileNotFoundError("No cache")):
            with pytest.raises(FileNotFoundError):
                _read_widget_from_cache(1, "kpi-revenue")

    def test_filter_results_match_manual(self, sample_cache):
        """Filtered read returns the same rows as manual Python filtering."""
        with patch(_PATCH_GET_CACHE_PATH, return_value=sample_cache):
            all_data = _read_widget_from_cache(1, "kpi-revenue")

        filters = [FilterParam(column="region", op="eq", value="North")]
        with patch(_PATCH_GET_CACHE_PATH, return_value=sample_cache):
            filtered = _read_widget_from_cache(1, "kpi-revenue", filters=filters)

        expected = [row for row in all_data.rows if row[0] == "North"]
        assert filtered.rows == expected
        assert filtered.row_count == len(expected)


# ---------------------------------------------------------------------------
# refresh_widget — cache path + fallback
# ---------------------------------------------------------------------------

def _make_dashboard(cache_status=None, data_context=None, widgets=None):
    d = MagicMock()
    d.cache_status = cache_status
    d.data_context = data_context
    d.widgets = widgets or []
    return d


def _make_db_returning(*results):
    """Return mock db where successive .query().filter().first() calls return *results*."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.side_effect = list(results)
    return db


@pytest.mark.asyncio
class TestRefreshWidgetCachePath:

    @patch(_PATCH_GET_CACHE_PATH)
    async def test_reads_from_cache_when_ready(self, mock_get_cache, sample_cache):
        mock_get_cache.return_value = sample_cache
        dashboard = _make_dashboard(cache_status="ready")
        db = _make_db_returning(dashboard)
        user = MagicMock(id="user-1")

        request = WidgetRefreshRequest(
            connection_id=1,
            sql="SELECT region, amount, order_date FROM orders",
            mapping={"type": "table", "columnConfig": [
                {"column": "region", "label": "Region"},
                {"column": "amount", "label": "Amount"},
                {"column": "order_date", "label": "Date"},
            ]},
            dashboard_id=1,
            widget_id="kpi-revenue",
        )

        response = await refresh_widget(request=request, current_user=user, db=db)

        assert response.row_count == 3
        assert response.source_columns == ["region", "amount", "order_date"]
        assert response.refreshed_at  # non-empty

    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_falls_back_when_no_cache(self, mock_get_connector):
        dashboard = _make_dashboard(cache_status=None)
        connection = MagicMock(id=1, user_id="user-1")
        db = _make_db_returning(dashboard, connection)
        user = MagicMock(id="user-1")

        connector = MagicMock()
        connector.execute_query.return_value = QueryResult(
            columns=["region", "amount"],
            rows=[("North", 100)],
            row_count=1,
            execution_time_ms=10.0,
        )
        mock_get_connector.return_value = connector

        request = WidgetRefreshRequest(
            connection_id=1,
            sql="SELECT region, amount FROM orders",
            mapping={"type": "table", "columnConfig": [
                {"column": "region", "label": "Region"},
                {"column": "amount", "label": "Amount"},
            ]},
            dashboard_id=1,
            widget_id="kpi-revenue",
        )

        response = await refresh_widget(request=request, current_user=user, db=db)

        assert response.row_count == 1
        connector.execute_query.assert_called_once()
        connector.close.assert_called_once()

    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_falls_back_when_building(self, mock_get_connector):
        dashboard = _make_dashboard(cache_status="building")
        connection = MagicMock(id=1, user_id="user-1")
        db = _make_db_returning(dashboard, connection)
        user = MagicMock(id="user-1")

        connector = MagicMock()
        connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[(1,)], row_count=1, execution_time_ms=5.0,
        )
        mock_get_connector.return_value = connector

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t",
            mapping={"type": "table", "columnConfig": [{"column": "a", "label": "A"}]},
            dashboard_id=1, widget_id="kpi-revenue",
        )

        response = await refresh_widget(request=request, current_user=user, db=db)
        assert response.row_count == 1
        connector.execute_query.assert_called_once()

    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_falls_back_when_failed(self, mock_get_connector):
        dashboard = _make_dashboard(cache_status="failed")
        connection = MagicMock(id=1, user_id="user-1")
        db = _make_db_returning(dashboard, connection)
        user = MagicMock(id="user-1")

        connector = MagicMock()
        connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[(1,)], row_count=1, execution_time_ms=5.0,
        )
        mock_get_connector.return_value = connector

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t",
            mapping={"type": "table", "columnConfig": [{"column": "a", "label": "A"}]},
            dashboard_id=1, widget_id="kpi-revenue",
        )

        response = await refresh_widget(request=request, current_user=user, db=db)
        assert response.row_count == 1
        connector.execute_query.assert_called_once()


# ---------------------------------------------------------------------------
# refresh_dashboard_widgets — bulk cache path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestBulkRefreshCachePath:

    @patch(_PATCH_GET_CACHE_PATH)
    async def test_reads_all_from_cache(self, mock_get_cache, sample_cache):
        mock_get_cache.return_value = sample_cache
        dashboard = _make_dashboard(
            cache_status="ready",
            widgets=[
                {
                    "id": "kpi-revenue",
                    "dataSource": {
                        "connectionId": 1,
                        "sql": "SELECT region, amount, order_date FROM orders",
                        "mapping": {"type": "table", "columnConfig": [
                            {"column": "region"}, {"column": "amount"}, {"column": "order_date"},
                        ]},
                    },
                },
                {
                    "id": "chart-monthly",
                    "dataSource": {
                        "connectionId": 1,
                        "sql": "SELECT month, total FROM monthly_summary",
                        "mapping": {"type": "table", "columnConfig": [
                            {"column": "month"}, {"column": "total"},
                        ]},
                    },
                },
            ],
        )
        db = _make_db_returning(dashboard)
        user = MagicMock(id="user-1")

        response = await refresh_dashboard_widgets(1, current_user=user, db=db)

        assert "kpi-revenue" in response.widgets
        assert "chart-monthly" in response.widgets
        assert "config" in response.widgets["kpi-revenue"]
        assert "config" in response.widgets["chart-monthly"]

    @patch(_PATCH_GET_CACHE_PATH)
    async def test_missing_widget_table_returns_error(self, mock_get_cache, sample_cache):
        mock_get_cache.return_value = sample_cache
        dashboard = _make_dashboard(
            cache_status="ready",
            widgets=[{
                "id": "nonexistent-widget",
                "dataSource": {
                    "connectionId": 1,
                    "sql": "SELECT a FROM b",
                    "mapping": {"type": "table", "columnConfig": [{"column": "a"}]},
                },
            }],
        )
        db = _make_db_returning(dashboard)
        user = MagicMock(id="user-1")

        response = await refresh_dashboard_widgets(1, current_user=user, db=db)

        assert "error" in response.widgets["nonexistent-widget"]
        assert "not found" in response.widgets["nonexistent-widget"]["error"]

    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_falls_back_to_source_db(self, mock_get_connector):
        """When no cache, bulk refresh falls back to source DB per-widget."""
        connection = MagicMock(id=1, user_id="user-1")
        dashboard = _make_dashboard(
            cache_status=None,
            widgets=[{
                "id": "w1",
                "dataSource": {
                    "connectionId": 1,
                    "sql": "SELECT a FROM t",
                    "mapping": {"type": "table", "columnConfig": [{"column": "a"}]},
                },
            }],
        )
        db = _make_db_returning(dashboard, connection)
        user = MagicMock(id="user-1")

        connector = MagicMock()
        connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[(1,)], row_count=1, execution_time_ms=5.0,
        )
        mock_get_connector.return_value = connector

        response = await refresh_dashboard_widgets(1, current_user=user, db=db)

        assert "config" in response.widgets["w1"]
        connector.execute_query.assert_called_once()
        connector.close.assert_called_once()


# ---------------------------------------------------------------------------
# Transform compatibility
# ---------------------------------------------------------------------------

class TestTransformCompatibility:

    def test_sqlite_and_source_produce_identical_config(self):
        """QueryResult from SQLite cache transforms identically to source DB."""
        from backend.services.widget_transform import transform_widget_data

        mapping = {"type": "table", "columnConfig": [
            {"column": "region", "label": "Region"},
            {"column": "amount", "label": "Amount"},
        ]}

        sqlite_result = QueryResult(
            columns=["region", "amount"],
            rows=[("North", 100.0), ("South", 200.0)],
            row_count=2,
            execution_time_ms=0.5,
        )

        source_result = QueryResult(
            columns=["region", "amount"],
            rows=[("North", 100.0), ("South", 200.0)],
            row_count=2,
            execution_time_ms=10.0,
        )

        assert transform_widget_data(sqlite_result, mapping) == \
               transform_widget_data(source_result, mapping)
