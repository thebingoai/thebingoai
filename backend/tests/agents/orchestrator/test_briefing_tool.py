import asyncio
import json
from unittest.mock import MagicMock, patch
import pytest
from backend.agents.orchestrator.orchestrator_briefing_tool import build_briefing_tools
from backend.agents.context import AgentContext


def _ctx():
    return AgentContext(
        user_id="u1",
        available_connections=[],
        connection_metadata=[],
        thread_id="t1",
    )


def test_emit_briefing_validates_payload():
    captured = {}

    def fake_factory():
        s = MagicMock()
        s.query.return_value.filter.return_value.first.return_value = MagicMock(
            id=42, user_id="u1", dashboard_id=1, status="generating"
        )
        captured["session"] = s
        return s

    tools = build_briefing_tools(_ctx(), db_session_factory=fake_factory, briefing_id=42)
    emit = next(t for t in tools if t.name == "emit_briefing")

    bad_payload = {"headline": "x", "deck": "y", "kpis": [], "sections": [], "key_takeaways": []}
    result = asyncio.run(emit.ainvoke({"payload": bad_payload}))
    assert "invalid" in result.lower() or "error" in result.lower()


def test_emit_briefing_persists_valid_payload():
    persisted = {}

    def fake_factory():
        s = MagicMock()
        briefing = MagicMock(id=42, user_id="u1", dashboard_id=1, status="generating", payload=None)
        s.query.return_value.filter.return_value.first.return_value = briefing
        persisted["briefing"] = briefing
        return s

    tools = build_briefing_tools(_ctx(), db_session_factory=fake_factory, briefing_id=42)
    emit = next(t for t in tools if t.name == "emit_briefing")

    good = {
        "headline": "Revenue held",
        "deck": "Topline tracked.",
        "kpis": [{"label": "MRR", "value": "$13,816"}],
        "sections": [{"heading": "1. Lift", "prose": "Strong."}],
        "key_takeaways": ["a", "b", "c"],
    }
    with patch("backend.agents.orchestrator.orchestrator_briefing_tool._post_chat_message") as post_msg, \
         patch("backend.agents.orchestrator.orchestrator_briefing_tool._emit_ws") as emit_ws:
        result = asyncio.run(emit.ainvoke({"payload": good}))

    assert "ready" in result.lower() or "ok" in result.lower()
    assert persisted["briefing"].status == "ready"
    assert persisted["briefing"].payload["headline"] == "Revenue held"
    post_msg.assert_called_once()
    emit_ws.assert_called_once()
