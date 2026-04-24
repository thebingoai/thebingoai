"""Unit tests for _do_analyze_dashboard and _materialize_sql_params."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.agents.context import AgentContext
from backend.agents.orchestrator.orchestrator_dashboard_tools import (
    _do_analyze_dashboard,
    _materialize_sql_params,
)
from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401


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
    d = Dashboard(user_id=user.id, title="Sales Dashboard", description="Revenue metrics", widgets=[])
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _make_context(user_id: str = "user-1") -> AgentContext:
    return AgentContext(user_id=user_id, available_connections=[1])


def _make_factory(db):
    return MagicMock(return_value=db)


# _execute_widget_sql is a no-op mock by default — tests set widget config directly
_NOOP_EXECUTE = AsyncMock(return_value=None)


# ---------------------------------------------------------------------------
# TestMaterializeSqlParams
# ---------------------------------------------------------------------------

class TestMaterializeSqlParams:
    def test_string_value_single_quoted(self):
        sql = "SELECT * FROM t WHERE col = %(_f0)s"
        result = _materialize_sql_params(sql, {"_f0": "hello"})
        assert result == "SELECT * FROM t WHERE col = 'hello'"

    def test_string_with_single_quote_escaped(self):
        sql = "SELECT * FROM t WHERE col = %(_f0)s"
        result = _materialize_sql_params(sql, {"_f0": "it's"})
        assert result == "SELECT * FROM t WHERE col = 'it''s'"

    def test_integer_value_unquoted(self):
        sql = "SELECT * FROM t WHERE id = %(_f0)s"
        result = _materialize_sql_params(sql, {"_f0": 42})
        assert result == "SELECT * FROM t WHERE id = 42"

    def test_none_becomes_null(self):
        sql = "SELECT * FROM t WHERE col = %(_f0)s"
        result = _materialize_sql_params(sql, {"_f0": None})
        assert result == "SELECT * FROM t WHERE col = NULL"

    def test_multiple_params_all_replaced(self):
        sql = "WHERE a = %(_f0)s AND b = %(_f1)s"
        result = _materialize_sql_params(sql, {"_f0": "x", "_f1": 10})
        assert result == "WHERE a = 'x' AND b = 10"

    def test_empty_params_returns_unchanged(self):
        sql = "SELECT 1"
        result = _materialize_sql_params(sql, {})
        assert result == "SELECT 1"


# ---------------------------------------------------------------------------
# TestAnalyzeDashboardNotFound
# ---------------------------------------------------------------------------

class TestAnalyzeDashboardNotFound:
    @pytest.mark.asyncio
    async def test_missing_dashboard_returns_error(self, db, user):
        context = _make_context()
        factory = _make_factory(db)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, factory, 9999)

        data = json.loads(result)
        assert data["success"] is False
        assert "not found" in data["message"]

    @pytest.mark.asyncio
    async def test_wrong_user_returns_error(self, db, dashboard):
        context = _make_context(user_id="other-user")
        factory = _make_factory(db)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, factory, dashboard.id)

        data = json.loads(result)
        assert data["success"] is False


# ---------------------------------------------------------------------------
# TestAnalyzeDashboardStructure
# ---------------------------------------------------------------------------

class TestAnalyzeDashboardStructure:
    @pytest.mark.asyncio
    async def test_top_level_fields_present(self, db, user, dashboard):
        context = _make_context()
        factory = _make_factory(db)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, factory, dashboard.id)

        data = json.loads(result)
        assert data["success"] is True
        assert data["dashboard_id"] == dashboard.id
        assert data["title"] == "Sales Dashboard"
        assert data["description"] == "Revenue metrics"
        assert data["focus"] == "general"
        assert data["filters_applied"] == []
        assert data["analysis"] == []

    @pytest.mark.asyncio
    async def test_focus_reflected_in_response(self, db, user, dashboard):
        context = _make_context()
        factory = _make_factory(db)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, factory, dashboard.id, focus="revenue")

        assert json.loads(result)["focus"] == "revenue"

    @pytest.mark.asyncio
    async def test_empty_focus_defaults_to_general(self, db, user, dashboard):
        context = _make_context()
        factory = _make_factory(db)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, factory, dashboard.id, focus="")

        assert json.loads(result)["focus"] == "general"


# ---------------------------------------------------------------------------
# TestKpiWidgetAnalysis
# ---------------------------------------------------------------------------

def _dashboard_with_widgets(db, user, widgets):
    d = Dashboard(user_id=user.id, title="T", widgets=widgets)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


class TestKpiWidgetAnalysis:
    @pytest.mark.asyncio
    async def test_kpi_fields_extracted(self, db, user):
        widgets = [{"id": "k1", "widget": {"type": "kpi", "config": {
            "label": "Revenue", "value": 125000, "prefix": "$", "suffix": None, "trend": "up",
        }}}]
        d = _dashboard_with_widgets(db, user, widgets)
        context = _make_context()

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, _make_factory(db), d.id)

        entry = json.loads(result)["analysis"][0]
        assert entry["type"] == "kpi"
        assert entry["label"] == "Revenue"
        assert entry["value"] == 125000
        assert entry["prefix"] == "$"
        assert entry["trend"] == "up"

    @pytest.mark.asyncio
    async def test_kpi_null_trend_included(self, db, user):
        widgets = [{"id": "k2", "widget": {"type": "kpi", "config": {
            "label": "Orders", "value": 300, "prefix": None, "suffix": "units", "trend": None,
        }}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        entry = json.loads(result)["analysis"][0]
        assert entry["trend"] is None
        assert entry["suffix"] == "units"


# ---------------------------------------------------------------------------
# TestChartWidgetAnalysis
# ---------------------------------------------------------------------------

class TestChartWidgetAnalysis:
    def _chart_widget(self, wid, datasets, labels=None):
        return {"id": wid, "widget": {"type": "chart", "config": {
            "type": "line", "title": "Monthly Revenue",
            "data": {"datasets": datasets, "labels": labels or []},
        }}}

    @pytest.mark.asyncio
    async def test_increasing_trend(self, db, user):
        datasets = [{"label": "Revenue", "data": [1000, 2000, 3000]}]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c1", datasets, ["Jan", "Feb", "Mar"])])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        stats = json.loads(result)["analysis"][0]["dataset_stats"][0]
        assert stats["trend"] == "increasing"
        assert stats["min"] == 1000
        assert stats["max"] == 3000
        assert stats["avg"] == 2000.0
        assert stats["total"] == 6000.0
        assert stats["change_pct"] == 200.0

    @pytest.mark.asyncio
    async def test_decreasing_trend(self, db, user):
        datasets = [{"label": "Costs", "data": [5000, 4000, 3000]}]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c2", datasets)])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        stats = json.loads(result)["analysis"][0]["dataset_stats"][0]
        assert stats["trend"] == "decreasing"
        assert stats["change_pct"] == -40.0

    @pytest.mark.asyncio
    async def test_flat_trend(self, db, user):
        datasets = [{"label": "Flat", "data": [500, 500, 500]}]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c3", datasets)])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        assert json.loads(result)["analysis"][0]["dataset_stats"][0]["trend"] == "flat"

    @pytest.mark.asyncio
    async def test_non_numeric_values_ignored(self, db, user):
        datasets = [{"label": "Mixed", "data": [100, None, "N/A", 200]}]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c4", datasets)])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        stats = json.loads(result)["analysis"][0]["dataset_stats"][0]
        assert stats["min"] == 100
        assert stats["max"] == 200
        assert stats["total"] == 300.0

    @pytest.mark.asyncio
    async def test_empty_dataset_no_stats_entry(self, db, user):
        datasets = [{"label": "Empty", "data": []}]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c5", datasets)])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        assert json.loads(result)["analysis"][0]["dataset_stats"] == []

    @pytest.mark.asyncio
    async def test_multiple_datasets_each_get_stats(self, db, user):
        datasets = [
            {"label": "Revenue", "data": [100, 200]},
            {"label": "Costs", "data": [50, 75]},
        ]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c6", datasets)])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        stats_list = json.loads(result)["analysis"][0]["dataset_stats"]
        assert len(stats_list) == 2
        assert {s["label"] for s in stats_list} == {"Revenue", "Costs"}

    @pytest.mark.asyncio
    async def test_label_count_matches_labels_list(self, db, user):
        datasets = [{"label": "Sales", "data": [10, 20]}]
        d = _dashboard_with_widgets(db, user, [self._chart_widget("c7", datasets, labels=["Q1", "Q2"])])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        assert json.loads(result)["analysis"][0]["label_count"] == 2


# ---------------------------------------------------------------------------
# TestTableWidgetAnalysis
# ---------------------------------------------------------------------------

class TestTableWidgetAnalysis:
    @pytest.mark.asyncio
    async def test_row_and_column_counts(self, db, user):
        widgets = [{"id": "t1", "widget": {"type": "table", "config": {
            "title": "Top Customers",
            "columns": ["name", "revenue", "orders"],
            "rows": [["Alice", 1000, 5], ["Bob", 800, 3]],
        }}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        entry = json.loads(result)["analysis"][0]
        assert entry["column_count"] == 3
        assert entry["row_count"] == 2

    @pytest.mark.asyncio
    async def test_empty_table_zero_counts(self, db, user):
        widgets = [{"id": "t2", "widget": {"type": "table", "config": {"title": "Empty", "columns": [], "rows": []}}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        entry = json.loads(result)["analysis"][0]
        assert entry["column_count"] == 0
        assert entry["row_count"] == 0


# ---------------------------------------------------------------------------
# TestTextWidgetAnalysis
# ---------------------------------------------------------------------------

class TestTextWidgetAnalysis:
    @pytest.mark.asyncio
    async def test_content_length(self, db, user):
        widgets = [{"id": "tx1", "widget": {"type": "text", "config": {"content": "Hello World"}}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        assert json.loads(result)["analysis"][0]["content_length"] == len("Hello World")

    @pytest.mark.asyncio
    async def test_null_content_zero_length(self, db, user):
        widgets = [{"id": "tx2", "widget": {"type": "text", "config": {"content": None}}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        assert json.loads(result)["analysis"][0]["content_length"] == 0


# ---------------------------------------------------------------------------
# TestFilterWidgetAnalysis
# ---------------------------------------------------------------------------

class TestFilterWidgetAnalysis:
    @pytest.mark.asyncio
    async def test_filter_controls_extracted(self, db, user):
        widgets = [{"id": "f1", "widget": {"type": "filter", "config": {"controls": [
            {"key": "date_ctrl", "label": "Date Range", "type": "date_range", "column": "order_date"},
            {"key": "reg_ctrl", "label": "Region", "type": "dropdown", "column": "region"},
        ]}}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        entry = json.loads(result)["analysis"][0]
        assert entry["type"] == "filter"
        assert len(entry["controls"]) == 2
        assert entry["controls"][0] == {"key": "date_ctrl", "label": "Date Range", "type": "date_range", "column": "order_date"}

    @pytest.mark.asyncio
    async def test_filter_widget_with_empty_controls(self, db, user):
        widgets = [{"id": "f2", "widget": {"type": "filter", "config": {"controls": []}}}]
        d = _dashboard_with_widgets(db, user, widgets)

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(_make_context(), _make_factory(db), d.id)

        assert json.loads(result)["analysis"][0]["controls"] == []


# ---------------------------------------------------------------------------
# TestFilterInjection
# ---------------------------------------------------------------------------

class TestFilterInjection:
    @pytest.mark.asyncio
    async def test_invalid_filters_json_returns_error(self, db, user, dashboard):
        context = _make_context()

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, _make_factory(db), dashboard.id, filters="not-json")

        data = json.loads(result)
        assert data["success"] is False
        assert "Invalid filters" in data["message"]

    @pytest.mark.asyncio
    async def test_empty_filters_runs_unfiltered(self, db, user, dashboard):
        context = _make_context()

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, _make_factory(db), dashboard.id, filters="")

        data = json.loads(result)
        assert data["success"] is True
        assert data["filters_applied"] == []

    @pytest.mark.asyncio
    async def test_filters_appear_in_filters_applied(self, db, user):
        widgets = [{"id": "k1", "widget": {"type": "kpi", "config": {"label": "Rev", "value": 0}},
                    "dataSource": {"connectionId": 1, "sql": "SELECT SUM(amount) AS value FROM orders", "mapping": {}}}]
        d = _dashboard_with_widgets(db, user, widgets)
        context = _make_context()
        filters_json = json.dumps([{"column": "region", "op": "eq", "value": "APAC"}])

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, _make_factory(db), d.id, filters=filters_json)

        data = json.loads(result)
        assert data["success"] is True
        assert len(data["filters_applied"]) == 1
        assert data["filters_applied"][0]["column"] == "region"

    @pytest.mark.asyncio
    async def test_filter_injected_into_widget_sql(self, db, user):
        """Verify inject_filters is called and SQL is modified before _execute_widget_sql."""
        widgets = [{"id": "k1", "widget": {"type": "kpi", "config": {"label": "Rev", "value": 0}},
                    "dataSource": {"connectionId": 1, "sql": "SELECT SUM(amount) AS value FROM orders", "mapping": {}}}]
        d = _dashboard_with_widgets(db, user, widgets)
        context = _make_context()
        filters_json = json.dumps([{"column": "order_date", "op": "gte", "value": "2026-01-01"}])

        captured_widgets = []

        async def _capture_widget(widget, *args, **kwargs):
            captured_widgets.append(json.dumps(widget.get("dataSource", {}).get("sql", "")))

        with patch("backend.agents.dashboard_tools._execute_widget_sql", side_effect=_capture_widget):
            await _do_analyze_dashboard(context, _make_factory(db), d.id, filters=filters_json)

        assert len(captured_widgets) == 1
        assert "2026-01-01" in captured_widgets[0]

    @pytest.mark.asyncio
    async def test_no_filter_injection_on_widgets_without_datasource(self, db, user):
        """Widgets without a dataSource skip _execute_widget_sql entirely."""
        # KPI with a static value and NO dataSource — purely config-driven
        widgets = [
            {"id": "k1", "widget": {"type": "kpi", "config": {"label": "Rev", "value": 50000}}},
        ]
        d = _dashboard_with_widgets(db, user, widgets)
        context = _make_context()
        filters_json = json.dumps([{"column": "region", "op": "eq", "value": "US"}])

        fresh_mock = AsyncMock(return_value=None)
        with patch("backend.agents.dashboard_tools._execute_widget_sql", fresh_mock):
            result = await _do_analyze_dashboard(context, _make_factory(db), d.id, filters=filters_json)

        # No dataSource on any widget → _execute_widget_sql never called
        fresh_mock.assert_not_called()
        assert json.loads(result)["success"] is True
        # Static value still surfaced correctly
        assert json.loads(result)["analysis"][0]["value"] == 50000


# ---------------------------------------------------------------------------
# TestMixedWidgetDashboard
# ---------------------------------------------------------------------------

class TestMixedWidgetDashboard:
    @pytest.mark.asyncio
    async def test_all_widget_types_coexist(self, db, user):
        widgets = [
            {"id": "k1", "widget": {"type": "kpi", "config": {"label": "Rev", "value": 50000, "prefix": "$", "suffix": None, "trend": "up"}}},
            {"id": "c1", "widget": {"type": "chart", "config": {"type": "bar", "title": "Sales",
                "data": {"datasets": [{"label": "Units", "data": [10, 20, 30]}], "labels": ["A", "B", "C"]}}}},
            {"id": "t1", "widget": {"type": "table", "config": {"title": "Details", "columns": ["col1", "col2"], "rows": [["a", 1]]}}},
            {"id": "tx1", "widget": {"type": "text", "config": {"content": "Note"}}},
            {"id": "f1", "widget": {"type": "filter", "config": {"controls": [
                {"key": "dt", "label": "Date", "type": "date_range", "column": "order_date"}
            ]}}},
        ]
        d = _dashboard_with_widgets(db, user, widgets)
        context = _make_context()

        with patch("backend.agents.dashboard_tools._execute_widget_sql", _NOOP_EXECUTE):
            result = await _do_analyze_dashboard(context, _make_factory(db), d.id)

        analysis = json.loads(result)["analysis"]
        assert len(analysis) == 5
        assert {e["type"] for e in analysis} == {"kpi", "chart", "table", "text", "filter"}
