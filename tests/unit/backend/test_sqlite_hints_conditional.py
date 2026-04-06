"""Tests for conditional SQLite dialect hints in dashboard agent prompts."""
import pytest
from unittest.mock import patch


class TestSqliteHintsConditional:
    def test_sqlite_hints_absent_without_plugin(self):
        """SQLite hints not in dashboard agent prompt when CSV plugin is not loaded."""
        from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt

        with patch("backend.agents.tool_registry.get_plugin_tool_builders", return_value={}):
            prompt = build_dashboard_agent_prompt(available_connections=[1])
            assert "SQLite" not in prompt
            assert "strftime" not in prompt

    def test_sqlite_hints_present_with_plugin(self):
        """SQLite hints included in dashboard agent prompt when CSV plugin is loaded."""
        from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt

        def fake_builder(ctx, dbf):
            return []

        with patch("backend.agents.tool_registry.get_plugin_tool_builders",
                    return_value={"create_dataset_from_upload": fake_builder}), \
             patch("backend.services.connection_context.load_context_file",
                    side_effect=FileNotFoundError):
            prompt = build_dashboard_agent_prompt(available_connections=[1])
            assert "SQLite" in prompt
            assert "strftime" in prompt
