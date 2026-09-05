"""The chart attached to a message must come from the FINAL tool trail.

`run_orchestrator` (REST) discarded `_run_judge_retry`'s steps and read chart
tool calls only from the initial invocation, so a retry that created or replaced
a chart shipped retry prose with the wrong chart — or none. The streaming path
already appended retry steps to `collected_steps` before resolving, so the two
transports disagreed on the same turn.

Uses `select_dashboard_widget` results throughout: their resolution is pure
(no query_result_store round-trip), so the test needs no Redis.
"""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agents.orchestrator import graph
from backend.agents.orchestrator.chat_chart_tools import resolve_chart_specs_from_tool_results
from backend.agents.orchestrator.response_judge import JudgeVerdict

_QUESTION = "chart the revenue on @q4"


def _ai_with_tool_call(tool_name: str, tc_id: str) -> AIMessage:
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": tool_name, "id": tc_id, "args": {}}]
    return msg


def _chart_pair(tc_id: str, widget_id: str) -> list:
    return [
        _ai_with_tool_call("select_dashboard_widget", tc_id),
        ToolMessage(
            content=json.dumps({"success": True, "dashboard_id": 7, "widget_id": widget_id}),
            tool_call_id=tc_id,
        ),
    ]


async def _run(monkeypatch, initial: list, retry: list | None):
    """Drive run_orchestrator with a scripted initial turn and (optional) retry."""
    context = SimpleNamespace(user_id="u1", thread_id="t1")
    orchestrator = MagicMock()
    returns = [{"messages": initial}]
    if retry is not None:
        returns.append({"messages": initial + retry})
    orchestrator.ainvoke = AsyncMock(side_effect=returns)

    monkeypatch.setattr(graph, "build_orchestrator_tools", lambda *a, **k: [])
    monkeypatch.setattr(graph, "_load_profile_if_missing", lambda *a, **k: None)
    monkeypatch.setattr(graph, "_render_orchestrator_prompt", AsyncMock(return_value=""))
    monkeypatch.setattr(graph, "_create_orchestrator_agent", lambda *a, **k: orchestrator)
    monkeypatch.setattr("backend.agents.callbacks.get_callbacks", lambda **k: [])
    monkeypatch.setattr(graph.settings, "judge_enabled", True)
    monkeypatch.setattr(graph.settings, "judge_highlight_enabled", False)

    verdicts = [JudgeVerdict(resolved=True, reason="ok")] if retry is None else [
        JudgeVerdict(resolved=False, reason="no chart", suggested_directive="show the chart"),
        JudgeVerdict(resolved=True, reason="ok"),
    ]
    monkeypatch.setattr(graph, "judge_response", AsyncMock(side_effect=verdicts))
    return await graph.run_orchestrator(_QUESTION, context)


@pytest.mark.asyncio
async def test_a_chart_from_the_first_pass_is_attached(monkeypatch):
    """Baseline: no retry, chart resolves as before."""
    out = await _run(monkeypatch, [
        HumanMessage(content=_QUESTION),
        *_chart_pair("tc1", "w-first"),
        AIMessage(content="Here it is."),
    ], retry=None)
    assert out["chart_specs"] == [
        {"kind": "dashboard_widget", "dashboard_id": 7, "widget_id": "w-first"}
    ]


@pytest.mark.asyncio
async def test_a_chart_created_only_during_the_retry_is_attached(monkeypatch):
    """The regression: the first pass answered in prose, the retry drew the chart,
    and the message was persisted with chart_specs=None."""
    out = await _run(
        monkeypatch,
        [HumanMessage(content=_QUESTION), AIMessage(content="Revenue rose.")],
        retry=[
            HumanMessage(content="<directive>"),
            *_chart_pair("tc2", "w-retry"),
            AIMessage(content="Here it is."),
        ],
    )
    assert out["chart_specs"] == [
        {"kind": "dashboard_widget", "dashboard_id": 7, "widget_id": "w-retry"}
    ]


@pytest.mark.asyncio
async def test_the_retrys_chart_replaces_the_first_passs_chart(monkeypatch):
    """Last successful chart call wins — the prose shipped is the retry's, so the
    chart beside it must be the retry's too."""
    out = await _run(
        monkeypatch,
        [
            HumanMessage(content=_QUESTION),
            *_chart_pair("tc1", "w-first"),
            AIMessage(content="Wrong widget."),
        ],
        retry=[
            HumanMessage(content="<directive>"),
            *_chart_pair("tc2", "w-retry"),
            AIMessage(content="Here it is."),
        ],
    )
    assert out["chart_specs"][0]["widget_id"] == "w-retry"


@pytest.mark.asyncio
async def test_rest_and_websocket_resolve_the_same_trail_identically(monkeypatch):
    """Transport parity: the WS path resolves over collected_steps (initial +
    appended retry steps); REST must reach the same answer for the same turn."""
    initial = [HumanMessage(content=_QUESTION), AIMessage(content="Revenue rose.")]
    retry = [
        HumanMessage(content="<directive>"),
        *_chart_pair("tc2", "w-retry"),
        AIMessage(content="Here it is."),
    ]
    rest = await _run(monkeypatch, initial, retry=retry)

    # What the streaming path feeds resolve_chart_specs_from_tool_results.
    steps = graph._extract_steps_from_messages(
        initial + retry, start_index=len(initial), base_step_number=0,
    )
    ws = resolve_chart_specs_from_tool_results(
        [(s["tool_name"], s["content"].get("result"))
         for s in steps if s["step_type"] == "tool_result"],
        "u1",
    )
    assert rest["chart_specs"] == ws


@pytest.mark.asyncio
async def test_a_turn_with_no_chart_tool_attaches_nothing(monkeypatch):
    out = await _run(monkeypatch, [
        HumanMessage(content="what is 2+2"), AIMessage(content="4"),
    ], retry=None)
    assert out["chart_specs"] is None
