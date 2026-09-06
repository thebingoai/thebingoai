"""A save call without widgets must come back as an instruction, not a validator error.

On the 2026-09-06 prod ladder four of sixty builds ended with the dashboard agent
calling `create_dashboard` with title, description and data_context but no
`widgets`. LangChain's argument validation answered "widgets: Field required"
before our code ran; the model re-issued the identical call and the orchestrator
gave up. `widgets` is now optional at the schema layer so the refusal is ours and
says what to do.
"""
import json

import pytest

from backend.agents.context import AgentContext
from backend.agents.dashboard_tools import build_inline_dashboard_tools
from backend.agents.orchestrator.dashboard_widget_verifier import MAX_TOTAL_WIDGETS


def _tools():
    context = AgentContext(user_id="u1", available_connections=[])
    create, update = build_inline_dashboard_tools(context, lambda: None)
    return create, update


@pytest.mark.asyncio
async def test_create_without_widgets_is_an_instruction_not_a_schema_error():
    create, _ = _tools()
    result = json.loads(await create.ainvoke({"title": "T", "description": "D", "data_context": {"x": 1}}))
    assert result["success"] is False
    assert result["code"] == "widgets_missing"
    assert "data_context does NOT carry widgets" in result["message"]
    assert "create_dashboard again" in result["message"]
    assert "not a failed build attempt" in result["message"]


@pytest.mark.asyncio
async def test_create_with_empty_widgets_same_instruction():
    create, _ = _tools()
    result = json.loads(await create.ainvoke({"title": "T", "description": "D", "widgets": []}))
    assert result["code"] == "widgets_missing"
    # The old empty-list guidance survives: an upstream error must be surfaced, not built over.
    assert "build_dashboard_context returned an error" in result["message"]


@pytest.mark.asyncio
async def test_update_without_widgets_names_itself():
    _, update = _tools()
    result = json.loads(await update.ainvoke({"dashboard_id": 1}))
    assert result["code"] == "widgets_missing"
    assert "Call update_dashboard again" in result["message"]


def test_tool_description_states_the_same_target_as_the_prompt():
    """The July mismatch was exactly this: the tool said "max 14" while the prompt
    said 15. The description is a literal, so pin it to the constant here."""
    create, _ = _tools()
    assert f"Target 9-{MAX_TOTAL_WIDGETS} data widgets" in create.description
    assert "not counted" in create.description
    assert "max 14" not in create.description
