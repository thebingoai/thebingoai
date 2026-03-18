"""Tests for backward compatibility when agent_mesh_enabled=False."""

import pytest
from unittest import mock

from backend.agents.context import AgentContext


@pytest.fixture
def context():
    return AgentContext(
        user_id="test-user",
        available_connections=[1, 2],
        thread_id="test-thread",
    )


def test_mesh_disabled_uses_inline_invocation(context):
    """When agent_mesh_enabled=False, orchestrator uses inline tools (no mesh dispatch)."""
    with mock.patch("backend.agents.orchestrator.graph.settings") as mock_settings:
        mock_settings.agent_mesh_enabled = False

        from backend.agents.orchestrator.graph import _build_legacy_tools
        tools = _build_legacy_tools(context, db_session_factory=None)

        tool_names = [t.name for t in tools]
        assert "data_agent" in tool_names
        assert "rag_agent" in tool_names
        assert "recall_memory" in tool_names
        # Should NOT have communication tools
        assert "sessions_list" not in tool_names
        assert "sessions_send" not in tool_names


def test_mesh_disabled_no_session_id(context):
    """Context without session_id uses inline tools even if mesh_enabled=True."""
    assert context.session_id is None

    with mock.patch("backend.agents.orchestrator.graph.settings") as mock_settings:
        mock_settings.agent_mesh_enabled = True

        from backend.agents.orchestrator.graph import _build_legacy_tools
        tools = _build_legacy_tools(context, db_session_factory=None)

        tool_names = [t.name for t in tools]
        assert "data_agent" in tool_names
        # No session_id means no mesh tools
        assert "sessions_list" not in tool_names


def test_dashboard_agent_inline_when_mesh_disabled():
    """Dashboard agent uses inline data tools when mesh disabled."""
    with mock.patch("backend.agents.dashboard_agent.tools.settings") as mock_settings:
        mock_settings.agent_mesh_enabled = False

        context = AgentContext(
            user_id="test-user",
            available_connections=[1],
        )

        from backend.agents.dashboard_agent.tools import build_dashboard_agent_tools

        # Mock db_session_factory
        mock_factory = mock.MagicMock()
        tools = build_dashboard_agent_tools(context, mock_factory)

        tool_names = [t.name for t in tools]
        # Should have inline data tools
        assert "list_tables" in tool_names
        assert "get_table_schema" in tool_names
        # Should NOT have communication tools
        assert "sessions_send" not in tool_names


def test_context_session_id_field():
    """AgentContext has session_id field, defaults to None."""
    ctx = AgentContext(user_id="u1", available_connections=[])
    assert ctx.session_id is None

    ctx2 = AgentContext(user_id="u1", available_connections=[], session_id="s1")
    assert ctx2.session_id == "s1"
