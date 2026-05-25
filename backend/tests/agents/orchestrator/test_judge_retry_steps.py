"""Tests for the Layer-4 judge-retry step extraction added so that tool calls
made during the retry pass are persisted as agent_steps and surfaced to the
frontend (e.g. dashboard "View Dashboard" button)."""
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agents.orchestrator.graph import (
    _extract_steps_from_messages,
    _run_judge_retry,
)
from backend.agents.orchestrator.response_judge import JudgeVerdict


def _ai_with_tool_call(tool_name: str, tc_id: str, args: dict) -> AIMessage:
    msg = AIMessage(content="")
    msg.tool_calls = [{"name": tool_name, "id": tc_id, "args": args}]
    return msg


# ---------------------------------------------------------------------------
# _extract_steps_from_messages
# ---------------------------------------------------------------------------

def test_extract_returns_empty_when_no_new_messages():
    base = [HumanMessage(content="q"), AIMessage(content="a")]
    assert _extract_steps_from_messages(base, start_index=len(base), base_step_number=0) == []


def test_extract_single_tool_call_and_result_pair():
    base = [HumanMessage(content="q")]
    new = [
        _ai_with_tool_call("create_dashboard", "tc1", {"request": "x"}),
        ToolMessage(content=json.dumps({"success": True, "dashboard_id": 7}), tool_call_id="tc1"),
    ]
    steps = _extract_steps_from_messages(base + new, start_index=len(base), base_step_number=10)

    assert len(steps) == 2
    call, result = steps
    assert call["step_type"] == "tool_call"
    assert call["tool_name"] == "create_dashboard"
    assert call["content"] == {"tool": "create_dashboard", "args": {"request": "x"}}
    assert call["step_number"] == 11
    assert result["step_type"] == "tool_result"
    assert result["tool_name"] == "create_dashboard"
    assert result["content"]["result"] == {"success": True, "dashboard_id": 7}
    assert result["step_number"] == 12


def test_extract_handles_non_json_tool_result_string():
    base = []
    new = [
        _ai_with_tool_call("foo", "tc1", {}),
        ToolMessage(content="plain text", tool_call_id="tc1"),
    ]
    steps = _extract_steps_from_messages(new, start_index=0, base_step_number=0)
    assert steps[1]["content"]["result"] == "plain text"


def test_extract_resolves_tool_name_via_tool_call_id():
    """A ToolMessage with an unknown tool_call_id falls back to 'unknown' so we
    never crash on malformed sequences."""
    base = []
    new = [ToolMessage(content="{}", tool_call_id="missing")]
    steps = _extract_steps_from_messages(new, start_index=0, base_step_number=0)
    assert steps[0]["tool_name"] == "unknown"


def test_extract_step_numbering_continues_from_base():
    new = [_ai_with_tool_call("a", "tc1", {}), ToolMessage(content="{}", tool_call_id="tc1")]
    steps = _extract_steps_from_messages(new, start_index=0, base_step_number=42)
    assert [s["step_number"] for s in steps] == [43, 44]


def test_extract_multi_tool_calls_in_single_ai_message():
    ai = AIMessage(content="")
    ai.tool_calls = [
        {"name": "a", "id": "1", "args": {}},
        {"name": "b", "id": "2", "args": {}},
    ]
    msgs = [ai, ToolMessage(content="{}", tool_call_id="1"), ToolMessage(content="{}", tool_call_id="2")]
    steps = _extract_steps_from_messages(msgs, start_index=0, base_step_number=0)
    # Walk order: both tool_calls flushed first from the AI message, then the
    # two ToolMessages in the order they appear.
    assert [s["tool_name"] for s in steps] == ["a", "b", "a", "b"]
    assert [s["step_type"] for s in steps] == ["tool_call", "tool_call", "tool_result", "tool_result"]


# ---------------------------------------------------------------------------
# _run_judge_retry — 4-tuple shape + retry_steps extraction
# ---------------------------------------------------------------------------

@pytest.fixture
def initial_verdict() -> JudgeVerdict:
    return JudgeVerdict(
        resolved=False,
        reason="initial unresolved",
        suggested_directive="call the tool",
        highlighted_response="",
    )


@pytest.mark.asyncio
async def test_run_judge_retry_returns_four_tuple_with_retry_steps(initial_verdict, monkeypatch):
    """Retry that successfully calls a tool surfaces those calls as retry_steps."""
    # Real orchestrator returns the full message history: base + directive +
    # newly produced messages. `_run_judge_retry` constructs
    # `base + [AIMessage(initial), HumanMessage(directive)]` (3 here), so the
    # mock must return that prefix plus the retry-side messages for
    # `_extract_steps_from_messages` to slice them out correctly.
    base = [HumanMessage(content="q")]
    full_retry_history = base + [
        AIMessage(content="initial"),
        HumanMessage(content="<directive>"),
        _ai_with_tool_call("dashboard_agent", "tc1", {"request": "x"}),
        ToolMessage(content=json.dumps({"success": True, "dashboard_id": 99}), tool_call_id="tc1"),
        AIMessage(content="Done."),
    ]

    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(return_value={"messages": full_retry_history})

    async def fake_judge(_q, _a):
        return JudgeVerdict(resolved=True, reason="ok", suggested_directive="", highlighted_response="")

    monkeypatch.setattr("backend.agents.orchestrator.graph.judge_response", fake_judge)

    answer, succeeded, meta, retry_steps = await _run_judge_retry(
        user_question="q",
        initial_answer="initial",
        initial_verdict=initial_verdict,
        orchestrator=orchestrator,
        base_messages=base,
    )

    assert succeeded is True
    assert answer == "Done."
    assert meta["judge_reason_initial"] == "initial unresolved"
    # retry_steps must contain the dashboard_agent tool call+result
    assert [s["tool_name"] for s in retry_steps] == ["dashboard_agent", "dashboard_agent"]
    assert [s["step_type"] for s in retry_steps] == ["tool_call", "tool_result"]
    assert retry_steps[1]["content"]["result"] == {"success": True, "dashboard_id": 99}


@pytest.mark.asyncio
async def test_run_judge_retry_returns_empty_steps_when_retry_errors(initial_verdict):
    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    answer, succeeded, meta, retry_steps = await _run_judge_retry(
        user_question="q",
        initial_answer="initial",
        initial_verdict=initial_verdict,
        orchestrator=orchestrator,
        base_messages=[HumanMessage(content="q")],
    )

    assert answer == "initial"
    assert succeeded is False
    assert retry_steps == []
    assert "RuntimeError" in meta["judge_reason_retry"]


@pytest.mark.asyncio
async def test_run_judge_retry_returns_empty_steps_when_retry_yields_no_answer(initial_verdict):
    orchestrator = MagicMock()
    orchestrator.ainvoke = AsyncMock(return_value={"messages": [HumanMessage(content="q")]})

    answer, succeeded, meta, retry_steps = await _run_judge_retry(
        user_question="q",
        initial_answer="initial",
        initial_verdict=initial_verdict,
        orchestrator=orchestrator,
        base_messages=[HumanMessage(content="q")],
    )

    assert answer == "initial"
    assert succeeded is False
    assert retry_steps == []
    assert meta["judge_reason_retry"] == "retry produced no answer"
