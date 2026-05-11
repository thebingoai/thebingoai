from unittest.mock import MagicMock
from backend.agents.orchestrator.graph import build_orchestrator_tools
from backend.agents.context import AgentContext


def test_briefing_tool_registered_when_briefing_id_set():
    ctx = AgentContext(
        user_id="u1", available_connections=[], connection_metadata=[],
        thread_id="t1", briefing_id=42,
    )
    factory = MagicMock()
    tools = build_orchestrator_tools(ctx, custom_agents=None, db_session_factory=factory)
    names = {t.name for t in tools}
    assert "emit_briefing" in names


def test_briefing_tool_absent_when_no_briefing_id():
    ctx = AgentContext(
        user_id="u1", available_connections=[], connection_metadata=[], thread_id="t1",
    )
    factory = MagicMock()
    tools = build_orchestrator_tools(ctx, custom_agents=None, db_session_factory=factory)
    names = {t.name for t in tools}
    assert "emit_briefing" not in names
