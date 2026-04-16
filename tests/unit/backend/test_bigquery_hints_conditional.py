"""Tests for conditional BigQuery dialect hints in dashboard agent prompts."""
from unittest.mock import patch


class TestBigQueryHintsConditional:
    def test_bigquery_hints_absent_without_plugin(self):
        """BigQuery hints not in dashboard agent prompt when plugin is not loaded."""
        from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt

        with patch("backend.connectors.factory.get_connector_registration", return_value=None):
            prompt = build_dashboard_agent_prompt(available_connections=[1])
            assert "BigQuery SQL Dialect" not in prompt
            assert "_TABLE_SUFFIX" not in prompt

    def test_bigquery_hints_present_with_plugin(self):
        """BigQuery hints included in dashboard agent prompt when plugin is loaded."""
        from backend.agents.dashboard_agent.prompts import build_dashboard_agent_prompt

        mock_reg = object()  # any truthy value — registration exists
        with patch("backend.connectors.factory.get_connector_registration", return_value=mock_reg), \
             patch("backend.services.connection_context.load_context_file",
                   side_effect=FileNotFoundError):
            prompt = build_dashboard_agent_prompt(available_connections=[1])
            assert "BigQuery SQL Dialect" in prompt
            assert "_TABLE_SUFFIX" in prompt
            assert "PARTITION_KEY" in prompt

    def test_bigquery_hints_in_get_default_section(self):
        """BigQuery hints appended to dashboard_agent tools section when plugin is loaded."""
        from backend.agents.profile_defaults import get_default_section

        mock_reg = object()
        with patch("backend.connectors.factory.get_connector_registration", return_value=mock_reg):
            content = get_default_section("dashboard_agent", "tools")
            assert content is not None
            assert "BigQuery SQL Dialect" in content

    def test_bigquery_hints_absent_from_get_default_section_without_plugin(self):
        """BigQuery hints not appended when plugin is not registered."""
        from backend.agents.profile_defaults import get_default_section

        with patch("backend.connectors.factory.get_connector_registration", return_value=None):
            content = get_default_section("dashboard_agent", "tools")
            assert content is not None
            assert "BigQuery SQL Dialect" not in content
