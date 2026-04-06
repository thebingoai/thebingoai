"""Tests for dynamic plugin tool inclusion in dashboard tools (Phase 3)
and dataset connection guards (Phase 4)."""
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from backend.agents.context import AgentContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(**overrides) -> AgentContext:
    defaults = dict(
        user_id="user-1",
        available_connections=[1, 2, 3],
    )
    defaults.update(overrides)
    return AgentContext(**defaults)


def _make_db_session_factory():
    return MagicMock()


# ===========================================================================
# Phase 3: Dynamic tool inclusion
# ===========================================================================

class TestOrchestratorPluginTools:
    def test_orchestrator_tools_include_dataset_tool_when_plugin_loaded(self):
        """create_dataset_from_upload appears when plugin tool builder is registered."""
        from backend.agents.orchestrator.orchestrator_dashboard_tools import build_dashboard_tools

        mock_tool = MagicMock()
        mock_tool.name = "create_dataset_from_upload"

        def fake_builder(ctx, db_factory):
            return [mock_tool]

        with patch("backend.agents.tool_registry.get_plugin_tool_builders",
                    return_value={"create_dataset_from_upload": fake_builder}):
            tools = build_dashboard_tools(_make_context(), _make_db_session_factory())
            tool_names = [getattr(t, "name", None) for t in tools]
            assert "create_dataset_from_upload" in tool_names

    def test_orchestrator_tools_exclude_dataset_tool_when_no_plugin(self):
        """create_dataset_from_upload absent when no plugin provides it."""
        from backend.agents.orchestrator.orchestrator_dashboard_tools import build_dashboard_tools

        with patch("backend.agents.tool_registry.get_plugin_tool_builders",
                    return_value={}):
            tools = build_dashboard_tools(_make_context(), _make_db_session_factory())
            tool_names = [getattr(t, "name", None) for t in tools]
            assert "create_dataset_from_upload" not in tool_names


class TestDashboardAgentPluginTools:
    def test_dashboard_agent_tools_include_merge_when_plugin_loaded(self):
        """merge_datasets appears when plugin tool builder is registered."""
        from backend.agents.dashboard_agent.tools import build_dashboard_agent_tools

        mock_tool = MagicMock()
        mock_tool.name = "merge_datasets"

        def fake_builder(ctx, db_factory):
            return [mock_tool]

        context = _make_context()
        db_factory = _make_db_session_factory()

        with patch("backend.agents.tool_registry.get_plugin_tool_builders",
                    return_value={"merge_datasets": fake_builder}), \
             patch("backend.agents.data_agent.tools.build_data_agent_tools", return_value=[]), \
             patch("backend.agents.dashboard_tools.build_dashboard_tools", return_value=[]), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.agent_mesh_enabled = False
            tools = build_dashboard_agent_tools(context, db_factory)
            tool_names = [getattr(t, "name", None) for t in tools]
            assert "merge_datasets" in tool_names

    def test_dashboard_agent_tools_exclude_merge_when_no_plugin(self):
        """merge_datasets absent when no plugin provides it."""
        from backend.agents.dashboard_agent.tools import build_dashboard_agent_tools

        context = _make_context()
        db_factory = _make_db_session_factory()

        with patch("backend.agents.tool_registry.get_plugin_tool_builders",
                    return_value={}), \
             patch("backend.agents.data_agent.tools.build_data_agent_tools", return_value=[]), \
             patch("backend.agents.dashboard_tools.build_dashboard_tools", return_value=[]), \
             patch("backend.config.settings") as mock_settings:
            mock_settings.agent_mesh_enabled = False
            tools = build_dashboard_agent_tools(context, db_factory)
            tool_names = [getattr(t, "name", None) for t in tools]
            assert "merge_datasets" not in tool_names


# ===========================================================================
# Phase 4: Dataset connection guards
# ===========================================================================

def _make_widgets_json(connection_id=1):
    """Create a minimal valid widgets_json string for create_dashboard."""
    widgets = [{
        "id": "kpi_1",
        "position": {"x": 0, "y": 0, "w": 3, "h": 2},
        "widget": {"type": "kpi", "config": {"label": "Total"}},
        "dataSource": {
            "connectionId": connection_id,
            "sql": "SELECT COUNT(*) AS value FROM data",
            "mapping": {"type": "kpi", "valueColumn": "value"},
        },
    }]
    return json.dumps(widgets)


class TestDashboardCreateGuard:
    @pytest.mark.asyncio
    async def test_dashboard_create_rejects_dataset_without_plugin(self):
        """Dataset connection rejected when CSV plugin not loaded."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        context = _make_context()

        mock_conn = MagicMock()
        mock_conn.db_type = "dataset"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_conn
        db_factory = MagicMock(return_value=mock_db)

        with patch("backend.agents.tool_registry.get_plugin_tool_builders", return_value={}):
            tools = build_dashboard_tools(context, db_factory)
            create_tool = [t for t in tools if getattr(t, "name", None) == "create_dashboard"][0]
            result_str = await create_tool.ainvoke({
                "title": "Test",
                "description": "Test",
                "widgets_json": _make_widgets_json(),
            })
            result = json.loads(result_str)
            assert result["success"] is False
            assert "enterprise" in result["message"].lower() or "csv connector" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_dashboard_create_allows_dataset_with_plugin(self):
        """Dataset connection allowed when CSV plugin is loaded."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        context = _make_context()

        mock_conn = MagicMock()
        mock_conn.db_type = "dataset"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_conn
        db_factory = MagicMock(return_value=mock_db)

        def fake_builder(ctx, dbf):
            return []

        with patch("backend.agents.tool_registry.get_plugin_tool_builders",
                    return_value={"create_dataset_from_upload": fake_builder}), \
             patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", new_callable=AsyncMock), \
             patch("backend.models.dashboard.Dashboard") as MockDash:
            mock_instance = MagicMock()
            mock_instance.id = 1
            MockDash.return_value = mock_instance

            tools = build_dashboard_tools(context, db_factory)
            create_tool = [t for t in tools if getattr(t, "name", None) == "create_dashboard"][0]
            result_str = await create_tool.ainvoke({
                "title": "Test",
                "description": "Test",
                "widgets_json": _make_widgets_json(),
            })
            result = json.loads(result_str)
            # Should not be rejected by the guard
            assert "csv connector" not in result.get("message", "").lower() or result["success"] is True

    @pytest.mark.asyncio
    async def test_dashboard_create_allows_postgres_without_plugin(self):
        """Postgres connection passes through without CSV plugin."""
        from backend.agents.dashboard_tools import build_dashboard_tools

        context = _make_context()

        mock_conn = MagicMock()
        mock_conn.db_type = "postgres"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_conn
        db_factory = MagicMock(return_value=mock_db)

        with patch("backend.agents.tool_registry.get_plugin_tool_builders", return_value={}), \
             patch("backend.agents.dashboard_tools._validate_widget_sql_schema", return_value=[]), \
             patch("backend.agents.dashboard_tools._execute_widget_sql", new_callable=AsyncMock), \
             patch("backend.models.dashboard.Dashboard") as MockDash:
            mock_instance = MagicMock()
            mock_instance.id = 1
            MockDash.return_value = mock_instance

            tools = build_dashboard_tools(context, db_factory)
            create_tool = [t for t in tools if getattr(t, "name", None) == "create_dashboard"][0]
            result_str = await create_tool.ainvoke({
                "title": "Test",
                "description": "Test",
                "widgets_json": _make_widgets_json(),
            })
            result = json.loads(result_str)
            # Guard should not trigger for postgres
            assert "csv connector" not in result.get("message", "").lower()


class TestDashboardContextGuard:
    def test_dashboard_context_rejects_dataset_without_plugin(self):
        """Dataset connection rejected in build_dashboard_context without plugin."""
        from backend.agents.dashboard_agent.tools import _build_dashboard_context_tool

        context = _make_context()

        mock_conn = MagicMock()
        mock_conn.db_type = "dataset"
        mock_conn.profiling_status = "ready"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_conn
        db_factory = MagicMock(return_value=mock_db)

        with patch("backend.agents.tool_registry.get_plugin_tool_builders", return_value={}):
            tool_fn = _build_dashboard_context_tool(context, db_factory)
            result_str = tool_fn.invoke({
                "connection_id": 1,
                "table_names": ["data"],
                "dimensions": ["col1"],
            })
            result = json.loads(result_str)
            assert result["success"] is False
            assert "enterprise" in result["message"].lower() or "csv connector" in result["message"].lower()

    def test_dashboard_context_allows_postgres_without_plugin(self):
        """Postgres connection passes through build_dashboard_context without plugin."""
        from backend.agents.dashboard_agent.tools import _build_dashboard_context_tool

        context = _make_context()

        mock_conn = MagicMock()
        mock_conn.db_type = "postgres"
        mock_conn.profiling_status = "ready"
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_conn
        db_factory = MagicMock(return_value=mock_db)

        with patch("backend.agents.tool_registry.get_plugin_tool_builders", return_value={}), \
             patch("backend.services.connection_context.load_context_file", return_value={
                 "tables": {
                     "users": {"schema": "public", "columns": {"id": {"role": "dimension", "type": "integer"}}},
                 },
                 "relationships": [],
             }):
            tool_fn = _build_dashboard_context_tool(context, db_factory)
            result_str = tool_fn.invoke({
                "connection_id": 1,
                "table_names": ["users"],
                "dimensions": ["id"],
            })
            result = json.loads(result_str)
            # Guard should not trigger for postgres
            assert "csv connector" not in result.get("message", "").lower()
