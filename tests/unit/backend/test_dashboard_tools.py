"""Unit tests for backend.agents.dashboard_tools — validation and SQL execution helpers."""

import json

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.agents.dashboard_tools import (
    _validate_data_source,
    _validate_widgets,
    _validate_widget_sql_schema,
    _attempt_sql_fix,
    _execute_widget_sql,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_data_source(**overrides):
    """Return a minimal valid dataSource dict, with optional overrides."""
    ds = {
        "connectionId": 1,
        "sql": "SELECT 1",
        "mapping": {"type": "kpi", "valueColumn": "v"},
    }
    ds.update(overrides)
    return ds


def _valid_widget(**overrides):
    """Return a minimal valid widget dict, with optional overrides."""
    w = {
        "id": "w1",
        "position": {"x": 0, "y": 0, "w": 6, "h": 3},
        "widget": {"type": "kpi", "config": {"label": "Test"}},
    }
    w.update(overrides)
    return w


def _make_mock_connection(cid=1, db_type="postgres"):
    """Build a lightweight mock DatabaseConnection."""
    conn = MagicMock()
    conn.id = cid
    conn.db_type = db_type
    return conn


def _make_db_session_factory(connection=None):
    """Return a callable that produces a mock Session pre-loaded with *connection*."""
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = connection
    factory = MagicMock(return_value=mock_session)
    return factory, mock_session


# ---------------------------------------------------------------------------
# TestValidateDataSource
# ---------------------------------------------------------------------------

class TestValidateDataSource:
    """Tests for _validate_data_source (pure validation, no I/O)."""

    def test_valid_complete_data_source_returns_none(self):
        ds = _valid_data_source()
        assert _validate_data_source(ds, "kpi", 0) is None

    def test_not_a_dict_returns_error(self):
        result = _validate_data_source("bad", "kpi", 0)
        assert result is not None
        assert "must be an object" in result

    def test_missing_connection_id_returns_error(self):
        ds = _valid_data_source()
        del ds["connectionId"]
        result = _validate_data_source(ds, "kpi", 0)
        assert result is not None
        assert "connectionId" in result

    def test_connection_id_not_int_returns_error(self):
        ds = _valid_data_source(connectionId="abc")
        result = _validate_data_source(ds, "kpi", 0)
        assert result is not None
        assert "integer" in result

    def test_missing_sql_returns_error(self):
        ds = _valid_data_source()
        del ds["sql"]
        result = _validate_data_source(ds, "kpi", 0)
        assert result is not None
        assert "sql" in result

    def test_empty_sql_returns_error(self):
        ds = _valid_data_source(sql="   ")
        result = _validate_data_source(ds, "kpi", 0)
        assert result is not None
        assert "non-empty" in result

    def test_mapping_type_mismatch_returns_error(self):
        ds = _valid_data_source()
        ds["mapping"]["type"] = "chart"  # mismatch with widget_type="kpi"
        result = _validate_data_source(ds, "kpi", 0)
        assert result is not None
        assert "must match" in result


# ---------------------------------------------------------------------------
# TestValidateWidgets
# ---------------------------------------------------------------------------

class TestValidateWidgets:
    """Tests for _validate_widgets (list-level validation)."""

    def test_valid_list_returns_none(self):
        widgets = [_valid_widget()]
        assert _validate_widgets(widgets) is None

    def test_widget_not_dict_returns_error(self):
        result = _validate_widgets(["not_a_dict"])
        assert result is not None
        assert "must be an object" in result

    def test_missing_id_returns_error(self):
        w = _valid_widget()
        del w["id"]
        result = _validate_widgets([w])
        assert result is not None
        assert "id" in result

    def test_missing_position_returns_error(self):
        w = _valid_widget()
        del w["position"]
        result = _validate_widgets([w])
        assert result is not None
        assert "position" in result

    def test_missing_widget_key_returns_error(self):
        w = _valid_widget()
        del w["widget"]
        result = _validate_widgets([w])
        assert result is not None
        assert "widget" in result

    def test_position_missing_required_field_returns_error(self):
        w = _valid_widget()
        del w["position"]["h"]
        result = _validate_widgets([w])
        assert result is not None
        assert "h" in result

    def test_invalid_widget_type_returns_error(self):
        w = _valid_widget()
        w["widget"]["type"] = "sparkline"  # invalid
        result = _validate_widgets([w])
        assert result is not None
        assert "widget.type" in result

    def test_valid_with_data_source_returns_none(self):
        w = _valid_widget(dataSource=_valid_data_source())
        assert _validate_widgets([w]) is None


# ---------------------------------------------------------------------------
# TestValidateWidgetSqlSchema
# ---------------------------------------------------------------------------

class TestValidateWidgetSqlSchema:
    """Tests for _validate_widget_sql_schema (cross-references SQL vs schema)."""

    def test_no_schema_file_returns_empty_warnings(self):
        """FileNotFoundError from load_schema_file should be swallowed."""
        widget = _valid_widget(
            dataSource=_valid_data_source(sql="SELECT id FROM users"),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            side_effect=FileNotFoundError,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert warnings == []

    def test_table_not_in_schema_gives_warning(self):
        schema = {"tables": [{"name": "orders", "columns": [{"name": "id"}]}]}
        widget = _valid_widget(
            dataSource=_valid_data_source(sql="SELECT id FROM users"),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            return_value=schema,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert len(warnings) == 1
        assert "users" in warnings[0].lower()
        assert "not found" in warnings[0].lower()

    def test_column_not_in_schema_gives_warning(self):
        schema = {"tables": [{"name": "users", "columns": [{"name": "id"}, {"name": "email"}]}]}
        widget = _valid_widget(
            dataSource=_valid_data_source(sql="SELECT nonexistent FROM users"),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            return_value=schema,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert len(warnings) == 1
        assert "nonexistent" in warnings[0].lower()

    def test_mapping_column_not_in_sql_output_gives_warning(self):
        schema = {"tables": [{"name": "users", "columns": [{"name": "id"}, {"name": "email"}]}]}
        mapping = {"type": "kpi", "valueColumn": "total_missing"}
        widget = _valid_widget(
            dataSource=_valid_data_source(
                sql="SELECT id FROM users",
                mapping=mapping,
            ),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            return_value=schema,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert len(warnings) == 1
        assert "total_missing" in warnings[0]

    def test_valid_sql_and_mapping_returns_no_warnings(self):
        schema = {"tables": [{"name": "users", "columns": [{"name": "id"}, {"name": "email"}]}]}
        mapping = {"type": "kpi", "valueColumn": "id"}
        widget = _valid_widget(
            dataSource=_valid_data_source(
                sql="SELECT id FROM users",
                mapping=mapping,
            ),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            return_value=schema,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert warnings == []

    def test_flat_schema_format(self):
        schema = {
            "tables": [
                {"name": "users", "columns": [{"name": "id"}, {"name": "email"}]},
            ],
        }
        mapping = {"type": "kpi", "valueColumn": "id"}
        widget = _valid_widget(
            dataSource=_valid_data_source(
                sql="SELECT id FROM users",
                mapping=mapping,
            ),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            return_value=schema,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert warnings == []

    def test_nested_schema_format(self):
        schema = {
            "schemas": {
                "public": {
                    "tables": {
                        "users": {
                            "columns": [{"name": "id"}],
                        },
                    },
                },
            },
        }
        mapping = {"type": "kpi", "valueColumn": "id"}
        widget = _valid_widget(
            dataSource=_valid_data_source(
                sql="SELECT id FROM users",
                mapping=mapping,
            ),
        )
        with patch(
            "backend.services.schema_discovery.load_schema_file",
            return_value=schema,
        ):
            warnings = _validate_widget_sql_schema([widget])
        assert warnings == []


# ---------------------------------------------------------------------------
# TestAttemptSqlFix
# ---------------------------------------------------------------------------

class TestAttemptSqlFix:
    """Tests for _attempt_sql_fix (async, LLM-powered SQL correction)."""

    def _default_patches(self):
        """Return a dict of common patches for _attempt_sql_fix tests."""
        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(
            return_value=json.dumps({
                "suggested_sql": "SELECT 1 AS v",
                "explanation": "fixed column name",
            }),
        )
        mock_settings = MagicMock()
        mock_settings.default_llm_provider = "openai"

        mock_reg = MagicMock()
        mock_reg.sql_dialect_hint = "PostgreSQL"

        return {
            "provider": mock_provider,
            "settings": mock_settings,
            "reg": mock_reg,
        }

    @pytest.mark.asyncio
    async def test_llm_returns_valid_json_returns_suggested_sql(self):
        mocks = self._default_patches()
        connection = _make_mock_connection()

        with (
            patch("backend.services.schema_discovery.load_schema_file", return_value={"tables": []}),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            result = await _attempt_sql_fix(
                sql="SELECT bad FROM t",
                error_message="column bad does not exist",
                connection=connection,
                mapping={"type": "kpi", "valueColumn": "v"},
                widget_id="w1",
            )
        assert result == "SELECT 1 AS v"

    @pytest.mark.asyncio
    async def test_no_schema_file_still_calls_llm(self):
        mocks = self._default_patches()
        connection = _make_mock_connection()

        with (
            patch("backend.services.schema_discovery.load_schema_file", side_effect=FileNotFoundError),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            result = await _attempt_sql_fix(
                sql="SELECT x FROM t",
                error_message="error",
                connection=connection,
                mapping={"type": "kpi"},
                widget_id="w1",
            )
        assert result == "SELECT 1 AS v"
        mocks["provider"].chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_raises_exception_returns_none(self):
        mocks = self._default_patches()
        mocks["provider"].chat = AsyncMock(side_effect=RuntimeError("LLM down"))
        connection = _make_mock_connection()

        with (
            patch("backend.services.schema_discovery.load_schema_file", return_value={"tables": []}),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            result = await _attempt_sql_fix(
                sql="SELECT x FROM t",
                error_message="error",
                connection=connection,
                mapping={"type": "kpi"},
                widget_id="w1",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json_returns_none(self):
        mocks = self._default_patches()
        mocks["provider"].chat = AsyncMock(return_value="not json at all")
        connection = _make_mock_connection()

        with (
            patch("backend.services.schema_discovery.load_schema_file", return_value={"tables": []}),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            result = await _attempt_sql_fix(
                sql="SELECT x FROM t",
                error_message="error",
                connection=connection,
                mapping={"type": "kpi"},
                widget_id="w1",
            )
        assert result is None

    @pytest.mark.asyncio
    async def test_llm_response_wrapped_in_code_blocks_is_parsed(self):
        mocks = self._default_patches()
        wrapped = '```json\n{"suggested_sql": "SELECT fixed", "explanation": "ok"}\n```'
        mocks["provider"].chat = AsyncMock(return_value=wrapped)
        connection = _make_mock_connection()

        with (
            patch("backend.services.schema_discovery.load_schema_file", return_value={"tables": []}),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            result = await _attempt_sql_fix(
                sql="SELECT x FROM t",
                error_message="error",
                connection=connection,
                mapping={"type": "kpi"},
                widget_id="w1",
            )
        assert result == "SELECT fixed"

    @pytest.mark.asyncio
    async def test_widget_title_included_in_prompt(self):
        mocks = self._default_patches()
        connection = _make_mock_connection()

        with (
            patch("backend.services.schema_discovery.load_schema_file", return_value={"tables": []}),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            await _attempt_sql_fix(
                sql="SELECT x FROM t",
                error_message="error",
                connection=connection,
                mapping={"type": "kpi"},
                widget_id="w1",
                widget_title="Average Price",
            )

        # Inspect the prompt sent to the LLM
        call_args = mocks["provider"].chat.call_args
        prompt_messages = call_args[0][0]  # first positional arg is messages list
        prompt_text = prompt_messages[0]["content"]
        assert "Average Price" in prompt_text
        assert "SEMANTIC CHECK" in prompt_text

    @pytest.mark.asyncio
    async def test_uses_dialect_hint_from_connector_registration(self):
        mocks = self._default_patches()
        mocks["reg"].sql_dialect_hint = "MySQL 8"
        connection = _make_mock_connection(db_type="mysql")

        with (
            patch("backend.services.schema_discovery.load_schema_file", return_value={"tables": []}),
            patch("backend.llm.factory.get_provider", return_value=mocks["provider"]),
            patch("backend.config.settings", mocks["settings"]),
            patch("backend.agents.dashboard_tools.get_connector_registration", return_value=mocks["reg"]),
            patch("backend.services.schema_utils.extract_table_names", return_value=set()),
            patch("backend.services.schema_utils.build_schema_summary", return_value=""),
        ):
            await _attempt_sql_fix(
                sql="SELECT x FROM t",
                error_message="error",
                connection=connection,
                mapping={"type": "kpi"},
                widget_id="w1",
            )

        call_args = mocks["provider"].chat.call_args
        prompt_text = call_args[0][0][0]["content"]
        assert "MySQL 8" in prompt_text


# ---------------------------------------------------------------------------
# TestExecuteWidgetSql
# ---------------------------------------------------------------------------

class TestExecuteWidgetSql:
    """Tests for _execute_widget_sql (async, modifies widget dict in-place)."""

    def _make_widget(self, **overrides):
        w = {
            "id": "kpi_1",
            "dataSource": {
                "connectionId": 1,
                "sql": "SELECT count(*) as val",
                "mapping": {"type": "kpi", "valueColumn": "val"},
            },
            "widget": {"type": "kpi", "config": {"label": "Total"}},
        }
        w.update(overrides)
        return w

    @pytest.mark.asyncio
    async def test_success_merges_config_into_widget(self):
        widget = self._make_widget()
        connection = _make_mock_connection()
        factory, mock_session = _make_db_session_factory(connection)

        mock_connector = MagicMock()
        mock_result = MagicMock()
        mock_result.row_count = 1
        mock_connector.execute_query.return_value = mock_result

        transformed = {"value": 42}

        with (
            patch("backend.agents.dashboard_tools.get_connector_for_connection", return_value=mock_connector),
            patch("backend.models.database_connection.DatabaseConnection", MagicMock()),
            patch("backend.services.widget_transform.transform_widget_data", return_value=transformed),
        ):
            await _execute_widget_sql(widget, factory)

        assert widget["widget"]["config"]["value"] == 42
        mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_data_source_returns_early(self):
        widget = _valid_widget()  # no dataSource key
        factory, _ = _make_db_session_factory()

        await _execute_widget_sql(widget, factory)
        # factory should never be called since we return early
        factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_not_found_returns_early(self):
        widget = self._make_widget()
        factory, mock_session = _make_db_session_factory(connection=None)

        with patch("backend.models.database_connection.DatabaseConnection", MagicMock()):
            await _execute_widget_sql(widget, factory)

        # No connector should be created
        assert widget["widget"]["config"] == {"label": "Total"}
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_first_execute_fails_llm_fix_succeeds(self):
        widget = self._make_widget()
        connection = _make_mock_connection()
        factory, _ = _make_db_session_factory(connection)

        mock_connector = MagicMock()
        mock_result_ok = MagicMock()
        mock_result_ok.row_count = 5
        # First call raises, second call succeeds (with fixed SQL)
        mock_connector.execute_query.side_effect = [
            RuntimeError("bad column"),
            mock_result_ok,
        ]

        transformed = {"value": 99}

        with (
            patch("backend.agents.dashboard_tools.get_connector_for_connection", return_value=mock_connector),
            patch("backend.models.database_connection.DatabaseConnection", MagicMock()),
            patch("backend.services.widget_transform.transform_widget_data", return_value=transformed),
            patch(
                "backend.agents.dashboard_tools._attempt_sql_fix",
                new_callable=AsyncMock,
                return_value="SELECT fixed_col AS val",
            ),
        ):
            await _execute_widget_sql(widget, factory)

        assert widget["widget"]["config"]["value"] == 99
        assert widget["dataSource"]["sql"] == "SELECT fixed_col AS val"
        mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_executions_fail_widget_unchanged(self):
        widget = self._make_widget()
        original_config = dict(widget["widget"]["config"])
        connection = _make_mock_connection()
        factory, _ = _make_db_session_factory(connection)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = RuntimeError("always fails")

        with (
            patch("backend.agents.dashboard_tools.get_connector_for_connection", return_value=mock_connector),
            patch("backend.models.database_connection.DatabaseConnection", MagicMock()),
            patch(
                "backend.agents.dashboard_tools._attempt_sql_fix",
                new_callable=AsyncMock,
                return_value="SELECT still_broken AS val",
            ),
        ):
            await _execute_widget_sql(widget, factory)

        assert widget["widget"]["config"] == original_config
        mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_fix_returns_none_widget_unchanged(self):
        widget = self._make_widget()
        original_config = dict(widget["widget"]["config"])
        connection = _make_mock_connection()
        factory, _ = _make_db_session_factory(connection)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = RuntimeError("fail")

        with (
            patch("backend.agents.dashboard_tools.get_connector_for_connection", return_value=mock_connector),
            patch("backend.models.database_connection.DatabaseConnection", MagicMock()),
            patch(
                "backend.agents.dashboard_tools._attempt_sql_fix",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await _execute_widget_sql(widget, factory)

        assert widget["widget"]["config"] == original_config
        mock_connector.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_connector_close_always_called_even_on_exception(self):
        widget = self._make_widget()
        connection = _make_mock_connection()
        factory, _ = _make_db_session_factory(connection)

        mock_connector = MagicMock()
        mock_connector.execute_query.side_effect = RuntimeError("boom")

        with (
            patch("backend.agents.dashboard_tools.get_connector_for_connection", return_value=mock_connector),
            patch("backend.models.database_connection.DatabaseConnection", MagicMock()),
            patch(
                "backend.agents.dashboard_tools._attempt_sql_fix",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await _execute_widget_sql(widget, factory)

        mock_connector.close.assert_called_once()
