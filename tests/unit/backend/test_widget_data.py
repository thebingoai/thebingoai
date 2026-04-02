"""Unit tests for backend.api.widget_data — inject_filters and async endpoints."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi import HTTPException

from backend.api.widget_data import inject_filters, refresh_widget, refresh_dashboard_widgets, suggest_fix
from backend.schemas.widget_data import (
    FilterParam,
    WidgetRefreshRequest,
    WidgetSuggestFixRequest,
)
from backend.connectors.base import QueryResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(user_id="user-1"):
    user = MagicMock()
    user.id = user_id
    return user


def _mock_db(first_return=None):
    """Return a MagicMock db session whose .query().filter().first() chain returns *first_return*."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = first_return
    return db


def _mock_connection(conn_id=1, user_id="user-1", db_type="postgres"):
    conn = MagicMock()
    conn.id = conn_id
    conn.user_id = user_id
    conn.db_type = db_type
    return conn


def _mock_connector(columns=None, rows=None, row_count=None, execution_time_ms=10.0):
    columns = columns or ["a"]
    rows = rows or [(1,)]
    if row_count is None:
        row_count = len(rows)
    connector = MagicMock()
    connector.execute_query.return_value = QueryResult(
        columns=columns, rows=rows, row_count=row_count, execution_time_ms=execution_time_ms,
    )
    return connector


# Patch targets:
#   - get_connector_for_connection is imported locally inside refresh_widget / refresh_dashboard_widgets
#     via "from backend.connectors.factory import get_connector_for_connection", so we patch it at its
#     source module.
#   - transform_widget_data is imported at module level, so we patch on backend.api.widget_data.
#   - load_schema_file is imported locally inside suggest_fix via
#     "from backend.services.schema_discovery import load_schema_file", so patch at source.
#   - get_provider is imported locally via "from backend.llm.factory import get_provider", patch at source.
#   - settings is imported locally via "from backend.config import settings", patch at source.
#   - _extract_table_names and _build_schema_summary are imported at module level (line 207), patch on
#     backend.api.widget_data.

_PATCH_CONNECTOR_FACTORY = "backend.connectors.factory.get_connector_for_connection"
_PATCH_TRANSFORM = "backend.api.widget_data.transform_widget_data"
_PATCH_LOAD_SCHEMA = "backend.services.schema_discovery.load_schema_file"
_PATCH_GET_PROVIDER = "backend.llm.factory.get_provider"
_PATCH_SETTINGS = "backend.config.settings"
_PATCH_EXTRACT_TABLES = "backend.api.widget_data._extract_table_names"
_PATCH_BUILD_SUMMARY = "backend.api.widget_data._build_schema_summary"


# ---------------------------------------------------------------------------
# TestInjectFilters — pure function, no mocking
# ---------------------------------------------------------------------------

class TestInjectFilters:
    def test_no_filters_returns_original(self):
        sql = "SELECT * FROM t"
        result_sql, params = inject_filters(sql, [])
        assert result_sql == sql
        assert params == {}

    def test_single_eq_filter(self):
        sql = "SELECT * FROM t"
        filters = [FilterParam(column="status", op="eq", value="active")]
        result_sql, params = inject_filters(sql, filters)
        assert '"status" = %(_f0)s' in result_sql
        assert params == {"_f0": "active"}

    def test_multiple_filters_and_conditions(self):
        sql = "SELECT * FROM t"
        filters = [
            FilterParam(column="age", op="gt", value=18),
            FilterParam(column="name", op="ilike", value="%john%"),
        ]
        result_sql, params = inject_filters(sql, filters)
        assert '"age" > %(_f0)s' in result_sql
        assert '"name" ILIKE %(_f1)s' in result_sql
        assert " AND " in result_sql
        assert params == {"_f0": 18, "_f1": "%john%"}

    def test_existing_where_appends_and(self):
        sql = "SELECT * FROM t WHERE x = 1"
        filters = [FilterParam(column="y", op="eq", value=2)]
        result_sql, params = inject_filters(sql, filters)
        assert "WHERE x = 1 AND " in result_sql
        assert '"y" = %(_f0)s' in result_sql
        assert params == {"_f0": 2}

    def test_existing_where_with_group_by_inserts_before(self):
        sql = "SELECT * FROM t WHERE x = 1 GROUP BY x"
        filters = [FilterParam(column="y", op="lte", value=10)]
        result_sql, params = inject_filters(sql, filters)
        assert "AND " in result_sql
        assert "GROUP BY x" in result_sql
        # AND clause must appear before GROUP BY
        and_pos = result_sql.index("AND")
        group_pos = result_sql.index("GROUP BY")
        assert and_pos < group_pos

    def test_no_where_with_order_by_inserts_where_before(self):
        sql = "SELECT * FROM t ORDER BY x"
        filters = [FilterParam(column="y", op="neq", value=0)]
        result_sql, params = inject_filters(sql, filters)
        assert "WHERE " in result_sql
        assert "ORDER BY x" in result_sql
        where_pos = result_sql.index("WHERE")
        order_pos = result_sql.index("ORDER BY")
        assert where_pos < order_pos

    def test_no_where_with_having_inserts_where_before(self):
        sql = "SELECT count(*) FROM t HAVING count(*) > 5"
        filters = [FilterParam(column="status", op="eq", value="ok")]
        result_sql, params = inject_filters(sql, filters)
        assert "WHERE " in result_sql
        where_pos = result_sql.index("WHERE")
        having_pos = result_sql.index("HAVING")
        assert where_pos < having_pos

    def test_column_names_double_quoted(self):
        sql = "SELECT * FROM t"
        filters = [
            FilterParam(column="MyCol", op="gte", value=5),
            FilterParam(column="other", op="lt", value=100),
        ]
        result_sql, _ = inject_filters(sql, filters)
        assert '"MyCol"' in result_sql
        assert '"other"' in result_sql


# ---------------------------------------------------------------------------
# TestRefreshWidget — mock db, connector, transform
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRefreshWidget:

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_happy_path(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        user = _mock_user()
        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {"labels": [1], "datasets": []}

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t", mapping={"type": "bar"}, limit=100,
        )

        response = await refresh_widget(request=request, current_user=user, db=db)

        assert response.config == {"labels": [1], "datasets": []}
        assert response.row_count == 1
        assert response.truncated is False
        assert response.execution_time_ms == 10.0
        assert response.refreshed_at  # non-empty string
        connector.close.assert_called_once()

    async def test_connection_not_found_404(self):
        db = _mock_db(None)
        user = _mock_user()
        request = WidgetRefreshRequest(
            connection_id=999, sql="SELECT 1", mapping={"type": "bar"},
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh_widget(request=request, current_user=user, db=db)
        assert exc_info.value.status_code == 404

    @patch(_PATCH_TRANSFORM, side_effect=ValueError("bad mapping"))
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_value_error_from_transform_400(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t", mapping={"type": "bar"},
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh_widget(request=request, current_user=_mock_user(), db=db)
        assert exc_info.value.status_code == 400
        assert "bad mapping" in exc_info.value.detail
        connector.close.assert_called_once()

    @patch(_PATCH_TRANSFORM, side_effect=RuntimeError("boom"))
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_generic_exception_500(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t", mapping={"type": "bar"},
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh_widget(request=request, current_user=_mock_user(), db=db)
        assert exc_info.value.status_code == 500
        connector.close.assert_called_once()

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_with_filters_injects_sql(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {}

        request = WidgetRefreshRequest(
            connection_id=1,
            sql="SELECT a FROM t",
            mapping={"type": "bar"},
            filters=[FilterParam(column="x", op="eq", value=42)],
        )

        await refresh_widget(request=request, current_user=_mock_user(), db=db)

        called_sql = connector.execute_query.call_args[0][0]
        assert '"x" = %(_f0)s' in called_sql
        called_params = connector.execute_query.call_args[1].get("params")
        assert called_params == {"_f0": 42}

    @patch(_PATCH_TRANSFORM, side_effect=RuntimeError("fail"))
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_connector_close_called_on_exception(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t", mapping={"type": "bar"},
        )

        with pytest.raises(HTTPException):
            await refresh_widget(request=request, current_user=_mock_user(), db=db)

        connector.close.assert_called_once()

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_chart_sql_passes_through_without_limit(self, mock_get_connector, mock_transform):
        """Verify the endpoint does not inject a LIMIT clause into chart SQL."""
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {}

        original_sql = "SELECT category, COUNT(*) AS cnt FROM orders GROUP BY category ORDER BY cnt DESC"
        request = WidgetRefreshRequest(
            connection_id=1, sql=original_sql, mapping={"type": "chart"},
        )

        await refresh_widget(request=request, current_user=_mock_user(), db=db)

        called_sql = connector.execute_query.call_args[0][0]
        assert called_sql == original_sql
        assert "LIMIT" not in called_sql.upper()

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_chart_sql_with_filters_no_limit_added(self, mock_get_connector, mock_transform):
        """Filters add WHERE clauses but must not inject a LIMIT."""
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {}

        request = WidgetRefreshRequest(
            connection_id=1,
            sql="SELECT region, SUM(sales) FROM orders GROUP BY region ORDER BY 2 DESC",
            mapping={"type": "chart"},
            filters=[FilterParam(column="status", op="eq", value="active")],
        )

        await refresh_widget(request=request, current_user=_mock_user(), db=db)

        called_sql = connector.execute_query.call_args[0][0]
        assert "LIMIT" not in called_sql.upper()
        assert '"status" = %(_f0)s' in called_sql

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_filter_options_sql_passes_through_without_limit(self, mock_get_connector, mock_transform):
        """Filter option queries should not have a LIMIT appended."""
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector(columns=["option_value"], rows=[("A",), ("B",)])
        mock_get_connector.return_value = connector
        mock_transform.return_value = {}

        original_sql = "SELECT DISTINCT region AS option_value FROM orders ORDER BY 1"
        request = WidgetRefreshRequest(
            connection_id=1, sql=original_sql,
            mapping={"type": "table", "columnConfig": [{"column": "option_value", "label": "Option"}]},
        )

        await refresh_widget(request=request, current_user=_mock_user(), db=db)

        called_sql = connector.execute_query.call_args[0][0]
        assert called_sql == original_sql
        assert "LIMIT" not in called_sql.upper()

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_sql_with_existing_limit_preserved(self, mock_get_connector, mock_transform):
        """User-provided LIMIT in SQL must be preserved as-is."""
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {}

        original_sql = "SELECT name FROM customers ORDER BY name LIMIT 50"
        request = WidgetRefreshRequest(
            connection_id=1, sql=original_sql, mapping={"type": "table"},
        )

        await refresh_widget(request=request, current_user=_mock_user(), db=db)

        called_sql = connector.execute_query.call_args[0][0]
        assert called_sql == original_sql


# ---------------------------------------------------------------------------
# TestRefreshDashboardWidgets — mock db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRefreshDashboardWidgets:

    def _make_dashboard(self, widgets=None):
        dashboard = MagicMock()
        dashboard.widgets = widgets
        dashboard.cache_status = None
        dashboard.cache_built_at = None
        return dashboard

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_all_widgets_success(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        dashboard = self._make_dashboard(widgets=[
            {"id": "w1", "dataSource": {"connectionId": 1, "sql": "SELECT 1", "mapping": {"type": "bar"}}},
            {"id": "w2", "dataSource": {"connectionId": 1, "sql": "SELECT 2", "mapping": {"type": "kpi"}}},
        ])
        db = MagicMock()
        # First call returns dashboard, subsequent calls return connection
        db.query.return_value.filter.return_value.first.side_effect = [dashboard, mock_conn, mock_conn]

        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {"key": "val"}

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        assert "w1" in response.widgets
        assert "w2" in response.widgets
        assert "config" in response.widgets["w1"]
        assert "config" in response.widgets["w2"]

    async def test_dashboard_not_found_404(self):
        db = _mock_db(None)

        with pytest.raises(HTTPException) as exc_info:
            await refresh_dashboard_widgets(dashboard_id=999, current_user=_mock_user(), db=db)
        assert exc_info.value.status_code == 404

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_skip_widgets_without_datasource(self, mock_get_connector, mock_transform):
        dashboard = self._make_dashboard(widgets=[
            {"id": "w1"},  # no dataSource
            {"id": "w2", "dataSource": {"connectionId": 1, "sql": "SELECT 1", "mapping": {"type": "bar"}}},
        ])
        mock_conn = _mock_connection()
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [dashboard, mock_conn]

        connector = _mock_connector()
        mock_get_connector.return_value = connector
        mock_transform.return_value = {}

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        assert "w1" not in response.widgets
        assert "w2" in response.widgets

    async def test_incomplete_datasource_per_widget_error(self):
        dashboard = self._make_dashboard(widgets=[
            {"id": "w1", "dataSource": {"connectionId": 1}},  # missing sql and mapping
        ])
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [dashboard]

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        assert "error" in response.widgets["w1"]
        assert "Incomplete dataSource" in response.widgets["w1"]["error"]

    async def test_connection_not_found_per_widget_error(self):
        dashboard = self._make_dashboard(widgets=[
            {"id": "w1", "dataSource": {"connectionId": 99, "sql": "SELECT 1", "mapping": {"type": "bar"}}},
        ])
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [dashboard, None]

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        assert "error" in response.widgets["w1"]
        assert "not found" in response.widgets["w1"]["error"]

    @patch(_PATCH_TRANSFORM)
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_per_widget_error_isolation(self, mock_get_connector, mock_transform):
        """One widget fails, the other succeeds."""
        mock_conn = _mock_connection()
        dashboard = self._make_dashboard(widgets=[
            {"id": "w1", "dataSource": {"connectionId": 1, "sql": "BAD SQL", "mapping": {"type": "bar"}}},
            {"id": "w2", "dataSource": {"connectionId": 1, "sql": "SELECT 1", "mapping": {"type": "bar"}}},
        ])
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [dashboard, mock_conn, mock_conn]

        # First connector call raises, second succeeds
        connector_fail = MagicMock()
        connector_fail.execute_query.side_effect = RuntimeError("query error")
        connector_ok = _mock_connector()
        mock_get_connector.side_effect = [connector_fail, connector_ok]
        mock_transform.return_value = {"ok": True}

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        assert "error" in response.widgets["w1"]
        assert "config" in response.widgets["w2"]
        connector_fail.close.assert_called_once()
        connector_ok.close.assert_called_once()

    async def test_empty_widgets_list(self):
        dashboard = self._make_dashboard(widgets=[])
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = dashboard

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        assert response.widgets == {}

    @patch(_PATCH_TRANSFORM, side_effect=RuntimeError("boom"))
    @patch(_PATCH_CONNECTOR_FACTORY)
    async def test_connector_close_always_called(self, mock_get_connector, mock_transform):
        mock_conn = _mock_connection()
        dashboard = self._make_dashboard(widgets=[
            {"id": "w1", "dataSource": {"connectionId": 1, "sql": "SELECT 1", "mapping": {"type": "bar"}}},
        ])
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [dashboard, mock_conn]

        connector = _mock_connector()
        mock_get_connector.return_value = connector

        response = await refresh_dashboard_widgets(
            dashboard_id=1, current_user=_mock_user(), db=db,
        )

        # Even though transform raised, connector.close() must still be called
        connector.close.assert_called_once()
        assert "error" in response.widgets["w1"]


# ---------------------------------------------------------------------------
# TestSuggestFix — mock db, LLM, schema
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSuggestFix:

    def _make_request(self, widget_title=None, widget_description=None):
        return WidgetSuggestFixRequest(
            connection_id=1,
            sql="SELECT foo FROM bar",
            error_message='column "foo" does not exist',
            mapping={"type": "bar", "x": "category"},
            widget_title=widget_title,
            widget_description=widget_description,
        )

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="schema info")
    @patch(_PATCH_EXTRACT_TABLES, return_value=["bar"])
    @patch(_PATCH_LOAD_SCHEMA, return_value={"tables": []})
    async def test_llm_returns_valid_json(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value='{"suggested_sql": "SELECT id FROM bar", "explanation": "Fixed column name"}'
        )
        mock_get_provider.return_value = mock_provider

        response = await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)

        assert response.suggested_sql == "SELECT id FROM bar"
        assert response.explanation == "Fixed column name"

    async def test_connection_not_found_404(self):
        db = _mock_db(None)

        with pytest.raises(HTTPException) as exc_info:
            await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)
        assert exc_info.value.status_code == 404

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="")
    @patch(_PATCH_EXTRACT_TABLES, return_value=[])
    @patch(_PATCH_LOAD_SCHEMA, side_effect=FileNotFoundError("no schema"))
    async def test_schema_file_not_found_proceeds(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value='{"suggested_sql": "SELECT 1", "explanation": "ok"}'
        )
        mock_get_provider.return_value = mock_provider

        response = await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)

        assert response.suggested_sql == "SELECT 1"
        # _extract_table_names and _build_schema_summary should NOT have been called
        # since load_schema_file raised FileNotFoundError
        mock_extract.assert_not_called()
        mock_build.assert_not_called()

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="")
    @patch(_PATCH_EXTRACT_TABLES, return_value=[])
    @patch(_PATCH_LOAD_SCHEMA, return_value={})
    async def test_strips_markdown_code_blocks(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value='```json\n{"suggested_sql": "SELECT 1", "explanation": "stripped"}\n```'
        )
        mock_get_provider.return_value = mock_provider

        response = await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)

        assert response.suggested_sql == "SELECT 1"
        assert response.explanation == "stripped"

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="")
    @patch(_PATCH_EXTRACT_TABLES, return_value=[])
    @patch(_PATCH_LOAD_SCHEMA, return_value={})
    async def test_llm_exception_500(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_get_provider.return_value = mock_provider

        with pytest.raises(HTTPException) as exc_info:
            await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)
        assert exc_info.value.status_code == 500

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="schema info")
    @patch(_PATCH_EXTRACT_TABLES, return_value=["bar"])
    @patch(_PATCH_LOAD_SCHEMA, return_value={"tables": []})
    async def test_with_widget_title_and_description(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value='{"suggested_sql": "SELECT price FROM bar", "explanation": "Used price column"}'
        )
        mock_get_provider.return_value = mock_provider

        request = self._make_request(widget_title="Average Price", widget_description="Shows avg prices")
        response = await suggest_fix(request=request, current_user=_mock_user(), db=db)

        # Verify the prompt contains title/description context
        call_args = mock_provider.chat.call_args
        prompt_text = call_args[0][0][0]["content"]
        assert "Average Price" in prompt_text
        assert "Shows avg prices" in prompt_text
        assert response.suggested_sql == "SELECT price FROM bar"

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="")
    @patch(_PATCH_EXTRACT_TABLES, return_value=[])
    @patch(_PATCH_LOAD_SCHEMA, return_value={})
    async def test_invalid_json_from_llm_500(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value="This is not valid JSON at all")
        mock_get_provider.return_value = mock_provider

        with pytest.raises(HTTPException) as exc_info:
            await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)
        assert exc_info.value.status_code == 500

    @patch(_PATCH_SETTINGS)
    @patch(_PATCH_GET_PROVIDER)
    @patch(_PATCH_BUILD_SUMMARY, return_value="")
    @patch(_PATCH_EXTRACT_TABLES, return_value=[])
    @patch(_PATCH_LOAD_SCHEMA, return_value={})
    async def test_response_structure(
        self, mock_load, mock_extract, mock_build, mock_get_provider, mock_settings,
    ):
        mock_conn = _mock_connection()
        db = _mock_db(mock_conn)
        mock_settings.default_llm_provider = "openai"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value='{"suggested_sql": "SELECT 1", "explanation": "all good"}'
        )
        mock_get_provider.return_value = mock_provider

        response = await suggest_fix(request=self._make_request(), current_user=_mock_user(), db=db)

        assert hasattr(response, "suggested_sql")
        assert hasattr(response, "explanation")
        assert isinstance(response.suggested_sql, str)
        assert isinstance(response.explanation, str)
