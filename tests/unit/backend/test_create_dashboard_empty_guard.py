"""Tool-boundary guard: create_dashboard must refuse zero-widget payloads."""
import json

import pytest
from unittest.mock import MagicMock

from backend.agents.dashboard_tools import build_inline_dashboard_tools


def _build_tool():
    context = MagicMock()
    context.user_id = "user-1"
    context.org_id = "org-1"
    db_session_factory = MagicMock()
    tools = build_inline_dashboard_tools(context, db_session_factory)
    # build_inline_dashboard_tools returns [create_dashboard, update_dashboard]
    return tools[0], db_session_factory


@pytest.mark.asyncio
async def test_create_dashboard_rejects_empty_widgets_list():
    """widgets=[] returns success=false and does not open a DB session."""
    create_dashboard, db_session_factory = _build_tool()

    result_json = await create_dashboard.ainvoke({
        "title": "Empty",
        "description": "should be rejected",
        "widgets": [],
        "data_context": None,
    })

    result = json.loads(result_json)
    assert result["success"] is False
    assert "zero widgets" in result["message"]
    # No session opened — the guard fires before any DB access.
    db_session_factory.assert_not_called()
