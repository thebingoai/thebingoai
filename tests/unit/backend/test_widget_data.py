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


class TestWidgetRefreshRequestSchema:

    def test_numeric_widget_id_coerced_to_str(self):
        # Agent-generated dashboards store numeric widget ids (e.g. 9329);
        # the refresh body must accept them, not 422.
        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT 1", mapping={"type": "bar"}, widget_id=9329,
        )
        assert request.widget_id == "9329"

    def test_widget_id_none_stays_none(self):
        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT 1", mapping={"type": "bar"},
        )
        assert request.widget_id is None

    @pytest.mark.parametrize("bad", [True, 9.5, ["w1"], {"id": 1}])
    def test_non_int_non_str_widget_id_rejected(self, bad):
        # Only real ints coerce; bools/floats/containers still 422.
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            WidgetRefreshRequest(
                connection_id=1, sql="SELECT 1", mapping={"type": "bar"}, widget_id=bad,
            )


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


class TestFilterNeverSilentlyDropped:
    """A filter that cannot be applied must surface, never render as unfiltered rows.

    Regression cover for the dashboard-filter bug: a filter naming a column the
    widget SQL can't reach used to be retried with the filter stripped, so the
    endpoint answered 200 with the full unfiltered result and no error.
    """

    def test_dimension_gate_binds_undeclared_columns_by_source_columns(self):
        """A declared dimension is gated by its `sources`. An undeclared column
        is gated by the column lists the context carries per source: kept when
        one of the widget's sources exposes it (dropping it would serve
        unfiltered rows as filtered), dropped when *another* source has it and
        this widget's don't (injecting it would 400 on every widget — 3433c24).
        A column no source in the context has at all is nobody's per-widget
        skip: it is injected so the engine names it, because dropping it is how
        a filter nothing can honour renders as a successful filtered answer."""
        from backend.api.widget_data import _dimension_applies_to_sources

        ctx = {
            "dimensions": {"session_date": {"column": "session_date",
                                            "sources": ["csv_261"]}},
            "sources": {
                "csv_261": {"columns": ["session_date", "session_minutes"]},
                "csv_9": {"columns": ["plan_tier"]},
            },
        }
        assert _dimension_applies_to_sources("session_date", ctx, ["csv_261"]) is True
        # Known dimension, but it lives on a table this widget doesn't read.
        assert _dimension_applies_to_sources("session_date", ctx, ["other_tbl"]) is False
        # Undeclared, but this widget's source has the column → binds.
        assert _dimension_applies_to_sources("session_minutes", ctx, ["csv_261"]) is True
        # Undeclared, and the column lives on a *different* dashboard source →
        # a real per-widget skip, the case 3433c24 fixed.
        assert _dimension_applies_to_sources("plan_tier", ctx, ["csv_261"]) is False
        # Undeclared and unknown to every source → inject, don't drop.
        assert _dimension_applies_to_sources("zzz_nope", ctx, ["csv_261"]) is True
        # Case is not meaning: the profiler's casing must not decide this.
        assert _dimension_applies_to_sources("Session_Minutes", ctx, ["CSV_261"]) is True

        # Through inject_filters with widget_sources populated, as the frontend
        # sends it: the undeclared-but-present filter reaches the SQL, and so
        # does the one no source knows — the engine gets to reject it by name.
        # (Quoting is dialect-specific; the bound params are the signal.)
        sql, params = inject_filters(
            "SELECT session_date, session_minutes FROM csv_261",
            [FilterParam(column="session_minutes", op="gte", value=30)],
            data_context=ctx, widget_sources=["csv_261"],
        )
        assert "WHERE" in sql.upper() and params == {"_f0": 30}
        sql, params = inject_filters(
            "SELECT session_date, session_minutes FROM csv_261",
            [FilterParam(column="zzz_nope", op="gte", value=30)],
            data_context=ctx, widget_sources=["csv_261"],
        )
        assert "WHERE" in sql.upper() and params == {"_f0": 30}
        # Only a column another source owns is dropped without running.
        sql, params = inject_filters(
            "SELECT session_date, session_minutes FROM csv_261",
            [FilterParam(column="plan_tier", op="eq", value="pro")],
            data_context=ctx, widget_sources=["csv_261"],
        )
        assert "WHERE" not in sql.upper() and params == {}

    def test_pick_target_scope_reads_dashboard_context_sources(self):
        """Dashboard contexts expose `sources[t].columns` as a list; connection
        contexts expose `tables[t].columns` as a dict. Both must resolve."""
        from backend.api.widget_data import _pick_target_scope

        class _T:
            def __init__(self, name):
                self.name = name

        scopes = [("outer", [_T("csv_261")]), ("inner", [_T("csv_261")])]

        dashboard_ctx = {"sources": {"csv_261": {"columns": ["session_minutes",
                                                            "session_date"]}}}
        assert _pick_target_scope(scopes, {"session_date"}, dashboard_ctx) == "inner"
        assert _pick_target_scope(scopes, {"zzz_nope"}, dashboard_ctx) is None

        connection_ctx = {"tables": {"csv_261": {"columns": {"session_date": {"type": "DATE"}}}}}
        assert _pick_target_scope(scopes, {"session_date"}, connection_ctx) == "inner"

        # Case comes from whoever typed the SQL and whoever profiled the table;
        # it must not decide whether a scope can bind the filter. Mismatched,
        # this returns None and the caller wraps the whole query instead of
        # pushing the WHERE down.
        mixed = [("outer", [_T("Orders")]), ("inner", [_T("Orders")])]
        mixed_ctx = {"sources": {"orders": {"columns": ["region", "amount"]}}}
        assert _pick_target_scope(mixed, {"Region"}, mixed_ctx) == "inner"

        # No context at all → keep the old "innermost real-table scope" behaviour.
        assert _pick_target_scope(scopes, {"anything"}, None) == "inner"

    @pytest.mark.asyncio
    async def test_failed_filtered_query_raises_instead_of_serving_unfiltered(self):
        """Every retry keeps the filter on, so an unappliable filter 500s rather
        than silently returning the unfiltered rows."""
        connection = MagicMock(id=1, db_type="postgres", user_id="user-1",
                               org_id=None, owner_scope_kind="user",
                               owner_scope_id="user-1")
        connector = MagicMock()
        connector.serves_from_plane = False
        connector.execute_query.side_effect = Exception('column "zzz_nope" does not exist')

        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT count(*) AS n FROM orders",
            mapping={"type": "kpi", "valueColumn": "n"},
            filters=[FilterParam(column="zzz_nope", op="gte", value="2099-01-01")],
        )

        with patch("backend.connectors.factory.get_connector_for_connection",
                   return_value=connector):
            with pytest.raises(HTTPException) as exc:
                await refresh_widget(request, _mock_user(), _mock_db(connection))

        assert exc.value.status_code == 500
        # Every attempt carried bound filter params; an unfiltered retry would
        # have called through with params=None.
        assert connector.execute_query.call_count > 0
        assert all(
            call.kwargs.get("params") is not None
            for call in connector.execute_query.call_args_list
        ), "a retry dropped the filter instead of failing"

    def test_sources_come_from_the_sql_not_the_stored_list(self):
        """`sources` is written once, when the agent creates the widget; every SQL
        editor rewrites `dataSource.sql` without touching it. Reading the stale
        list drops a valid filter for the table the SQL actually names, and the
        query then succeeds unfiltered."""
        ctx = {
            "dimensions": {"event_date": {"column": "event_date",
                                          "sources": ["shipments"]}},
            "sources": {
                "orders": {"columns": ["order_date", "amount"]},
                "shipments": {"columns": ["event_date", "amount"]},
            },
        }
        # Widget was repointed orders → shipments; `sources` still says orders.
        sql, params = inject_filters(
            "SELECT event_date, amount FROM shipments",
            [FilterParam(column="event_date", op="gte", value="2026-01-01")],
            data_context=ctx, widget_sources=["orders"],
        )
        assert "WHERE" in sql.upper() and params == {"_f0": "2026-01-01"}

        # The reverse still holds: a filter for a table this SQL doesn't read
        # is dropped, whatever the stored list claims.
        sql, params = inject_filters(
            "SELECT order_date, amount FROM orders",
            [FilterParam(column="event_date", op="gte", value="2026-01-01")],
            data_context=ctx, widget_sources=["shipments"],
        )
        assert "WHERE" not in sql.upper() and params == {}

    def test_undeclared_column_on_an_unprofiled_table_is_injected(self):
        """Hand-edited SQL can name a table the context never described. Nothing
        can rule the filter out there, so inject and let the engine complain —
        the alternative is answering a filtered request with every row."""
        ctx = {"dimensions": {}, "sources": {"orders": {"columns": ["region"]}}}
        sql, params = inject_filters(
            "SELECT region FROM orders_2026_archive",
            [FilterParam(column="region", op="eq", value="EMEA")],
            data_context=ctx, widget_sources=["orders"],
        )
        assert "WHERE" in sql.upper() and params == {"_f0": "EMEA"}

    @pytest.mark.parametrize("sql,branches,dialect", [
        # Bare UNION / EXCEPT / INTERSECT are Postgres-side spellings; the
        # BigQuery parser requires the ALL / DISTINCT qualifier.
        ("SELECT event_date, amount FROM current_sales "
         "UNION ALL SELECT event_date, amount FROM archived_sales", 2, "bigquery"),
        ("SELECT event_date, amount FROM current_sales "
         "UNION DISTINCT SELECT event_date, amount FROM archived_sales", 2, "bigquery"),
        ("SELECT event_date, amount FROM current_sales "
         "UNION SELECT event_date, amount FROM archived_sales", 2, "postgres"),
        ("SELECT event_date, amount FROM current_sales "
         "EXCEPT SELECT event_date, amount FROM archived_sales", 2, "postgres"),
        ("(SELECT event_date, amount FROM current_sales) "
         "INTERSECT (SELECT event_date, amount FROM archived_sales)", 2, "postgres"),
        ("SELECT event_date, amount FROM current_sales "
         "UNION ALL SELECT event_date, amount FROM archived_sales "
         "UNION ALL SELECT event_date, amount FROM cold_sales", 3, "postgres"),
    ])
    def test_every_set_operation_branch_is_filtered(self, sql, branches, dialect):
        """_pick_target_scope returns ONE scope, so a UNION used to get its WHERE
        on a single branch while the others kept contributing unfiltered rows —
        and the combined query still returned 200."""
        ctx = {"sources": {t: {"columns": ["event_date", "amount"]}
                           for t in ("current_sales", "archived_sales", "cold_sales")}}
        out, params = inject_filters(
            sql, [FilterParam(column="event_date", op="gte", value="2026-01-01")],
            data_context=ctx, widget_sources=None, dialect=dialect,
        )
        assert out.upper().count("WHERE") == branches, out
        assert not out.startswith("SELECT * FROM ("), "fell back to the subquery wrap"
        # One placeholder name reused across branches → one bound value.
        assert params == {"_f0": "2026-01-01"}

    def test_a_set_branch_that_cannot_bind_wraps_the_whole_result(self):
        """Partially filtering a set operation is never right: when one branch
        can't take the condition, wrap the combined result instead."""
        ctx = {"sources": {"current_sales": {"columns": ["event_date", "amount"]},
                           "legacy_sales": {"columns": ["amount"]}}}
        out, params = inject_filters(
            "SELECT event_date, amount FROM current_sales "
            "UNION ALL SELECT NULL AS event_date, amount FROM legacy_sales",
            [FilterParam(column="event_date", op="gte", value="2026-01-01")],
            data_context=ctx, widget_sources=None, dialect="postgres",
        )
        assert out.startswith("SELECT * FROM ("), out
        assert out.upper().count("WHERE") == 1
        assert params == {"_f0": "2026-01-01"}

    def test_union_reaches_the_connector_filtered_on_both_branches(self):
        """End-to-end through the endpoint, not just the injector."""
        connection = MagicMock(id=1, db_type="postgres", user_id="user-1",
                               org_id=None, owner_scope_kind="user",
                               owner_scope_id="user-1")
        connector = MagicMock()
        connector.serves_from_plane = False
        connector.execute_query.return_value = QueryResult(
            columns=["region"], rows=[("EMEA",)], row_count=1, execution_time_ms=1.0,
        )
        request = WidgetRefreshRequest(
            connection_id=1,
            sql="SELECT region FROM current_sales UNION ALL SELECT region FROM archived_sales",
            mapping={"type": "table", "columnConfig": [{"column": "region"}]},
            filters=[FilterParam(column="region", op="eq", value="EMEA")],
        )
        resp = _run_refresh(request, connection, connector)
        assert resp is not None
        executed = connector.execute_query.call_args.args[0]
        assert executed.upper().count("WHERE") == 2, executed


def _run_refresh(request, connection, connector):
    """Drive refresh_widget synchronously with a mocked connector.

    `_mock_db` stops after one `.filter()`, but `_readable_connection` chains two
    (id, then owner), so the connection it resolves would be an auto-generated
    mock whose `db_type` isn't a real dialect. Self-returning filters keep the
    connection this test configured.
    """
    import asyncio
    db = MagicMock()
    q = db.query.return_value
    q.filter.return_value = q
    q.join.return_value = q
    q.first.return_value = connection
    with patch("backend.connectors.factory.get_connector_for_connection",
               return_value=connector):
        return asyncio.run(refresh_widget(request, _mock_user(), db))


class TestTruncatedResults:
    """A capped result must never be aggregated client-side and returned as a
    success — `settings.max_query_rows` clamps every connector and the DuckDB
    runner, so a KPI over raw rows sums only the prefix."""

    def test_truncated_flag_reaches_the_response(self):
        connection = MagicMock(id=1, db_type="postgres", user_id="user-1",
                               org_id=None, owner_scope_kind="user",
                               owner_scope_id="user-1")
        connector = MagicMock()
        connector.serves_from_plane = False
        connector.execute_query.return_value = QueryResult(
            columns=["a"], rows=[(1,)], row_count=1, execution_time_ms=1.0,
            truncated=True,
        )
        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT a FROM t",
            mapping={"type": "table", "columnConfig": [{"column": "a"}]},
        )
        resp = _run_refresh(request, connection, connector)
        assert resp.truncated is True, "truncation was hardcoded away"

    def test_truncated_kpi_is_rejected_not_summed(self):
        connection = MagicMock(id=1, db_type="postgres", user_id="user-1",
                               org_id=None, owner_scope_kind="user",
                               owner_scope_id="user-1")
        connector = MagicMock()
        connector.serves_from_plane = False
        connector.execute_query.return_value = QueryResult(
            columns=["v"], rows=[(1,), (2,)], row_count=2, execution_time_ms=1.0,
            truncated=True,
        )
        request = WidgetRefreshRequest(
            connection_id=1, sql="SELECT v FROM t",
            mapping={"type": "kpi", "valueColumn": "v", "aggregation": "sum"},
        )
        with pytest.raises(HTTPException) as exc:
            _run_refresh(request, connection, connector)
        assert exc.value.status_code == 400
        assert "truncated" in str(exc.value.detail).lower()
