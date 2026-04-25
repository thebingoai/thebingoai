"""Unit tests for backend.agents.orchestrator.manage_tool — dispatch + payload validation."""

import json
import pytest
from unittest.mock import MagicMock, patch

from backend.agents.context import AgentContext
from backend.agents.orchestrator.manage_tool import build_manage_tool, _DISPATCH


def _agent_ctx() -> AgentContext:
    return AgentContext(user_id="user-1", available_connections=[], thread_id="t1", team_id=None)


def _fake_factory():
    """Empty stand-in for db_session_factory — manage_tool only checks it's truthy
    in the build step; the underlying tools are mocked, so no DB access happens."""
    return MagicMock()


class _RecordingTool:
    """Minimal duck-typed BaseTool stand-in: only `.name` + `.ainvoke(kwargs)` are
    used by manage_tool's dispatcher. Records the kwargs it receives so tests
    can assert on the payload that reached the underlying tool."""

    def __init__(self, name: str, record: dict):
        self.name = name
        self._record = record

    async def ainvoke(self, kwargs: dict) -> str:
        self._record[self.name] = kwargs
        return json.dumps({"success": True, "tool": self.name, "kwargs": kwargs})


def _stub_tool(name: str, last_kwargs: dict):
    return _RecordingTool(name, last_kwargs)


@pytest.fixture
def manage_with_stubs():
    """Build a manage tool whose underlying skill / profile / soul / dashboard
    tools are stubs that record their kwargs."""
    last_kwargs: dict[str, dict] = {}

    skill_stubs = [
        _stub_tool(n, last_kwargs)
        for n in ("manage_skill", "get_skill", "use_skill", "list_skills", "handle_suggestion")
    ]
    profile_stubs = [_stub_tool(n, last_kwargs) for n in ("write_profile", "read_profile")]
    soul_stubs = [_stub_tool("update_personality", last_kwargs)]
    dashboard_stubs = [
        _stub_tool(n, last_kwargs)
        for n in (
            "create_dashboard", "update_dashboard", "list_dashboards",
            "list_connections", "read_dashboard", "analyze_dashboard",
        )
    ]

    with patch("backend.agents.orchestrator.manage_tool.build_skill_tools", return_value=skill_stubs), \
         patch("backend.agents.orchestrator.manage_tool.build_profile_tools", return_value=profile_stubs), \
         patch("backend.agents.orchestrator.manage_tool.build_soul_tools", return_value=soul_stubs), \
         patch("backend.agents.orchestrator.manage_tool.build_dashboard_tools", return_value=dashboard_stubs):
        manage = build_manage_tool(_agent_ctx(), _fake_factory())
        assert manage is not None
        yield manage, last_kwargs


# ---------------------------------------------------------------------------
# Dispatch table is complete + every entry round-trips
# ---------------------------------------------------------------------------


def test_dispatch_table_covers_every_documented_pair():
    expected_pairs = {
        ("skill", "create"), ("skill", "update"), ("skill", "delete"),
        ("skill", "get"), ("skill", "list"), ("skill", "use"),
        ("skill", "suggestion"),
        ("profile", "read"), ("profile", "write"),
        ("soul", "propose"), ("soul", "apply"),
        ("connection", "list"),
        ("dashboard", "list"),
    }
    assert set(_DISPATCH.keys()) == expected_pairs


@pytest.mark.parametrize("domain,action,payload,expected_tool", [
    ("skill",     "create",     {"name": "x", "description": "d"},        "manage_skill"),
    ("skill",     "update",     {"skill_name": "x"},                       "manage_skill"),
    ("skill",     "delete",     {"skill_name": "x"},                       "manage_skill"),
    ("skill",     "get",        {"name": "x"},                             "get_skill"),
    ("skill",     "list",       {},                                         "list_skills"),
    ("skill",     "use",        {"skill_name": "x", "params": {"a": 1}},   "use_skill"),
    ("skill",     "suggestion", {"decision": "check"},                     "handle_suggestion"),
    ("profile",   "read",       {},                                         "read_profile"),
    ("profile",   "write",      {"section": "soul", "content": "hi"},      "write_profile"),
    ("soul",      "propose",    {"proposed_soul": "name: Aria"},           "update_personality"),
    ("soul",      "apply",      {"proposed_soul": "name: Aria"},           "update_personality"),
    ("connection","list",       {},                                         "list_connections"),
    ("dashboard", "list",       {},                                         "list_dashboards"),
])
@pytest.mark.asyncio
async def test_each_pair_dispatches_to_underlying_tool(
    manage_with_stubs, domain, action, payload, expected_tool,
):
    manage, last_kwargs = manage_with_stubs
    result = await manage.ainvoke({"domain": domain, "action": action, "payload": payload})
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["tool"] == expected_tool
    assert expected_tool in last_kwargs


# ---------------------------------------------------------------------------
# Payload transforms: action="create"/"update"/"delete" reach manage_skill;
#                     params dict gets re-serialized as params_json for use_skill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_create_passes_action_create_kwarg(manage_with_stubs):
    manage, last_kwargs = manage_with_stubs
    await manage.ainvoke({
        "domain": "skill", "action": "create",
        "payload": {"name": "x", "description": "d", "instructions": "do thing"},
    })
    kwargs = last_kwargs["manage_skill"]
    assert kwargs["action"] == "create"
    assert kwargs["name"] == "x"
    assert kwargs["instructions"] == "do thing"


@pytest.mark.asyncio
async def test_skill_use_serializes_params_dict_to_json(manage_with_stubs):
    manage, last_kwargs = manage_with_stubs
    await manage.ainvoke({
        "domain": "skill", "action": "use",
        "payload": {"skill_name": "x", "params": {"region": "Dublin", "limit": 10}},
    })
    kwargs = last_kwargs["use_skill"]
    assert kwargs["skill_name"] == "x"
    assert json.loads(kwargs["params_json"]) == {"region": "Dublin", "limit": 10}


@pytest.mark.asyncio
async def test_soul_propose_includes_reason(manage_with_stubs):
    manage, last_kwargs = manage_with_stubs
    await manage.ainvoke({
        "domain": "soul", "action": "propose",
        "payload": {"proposed_soul": "name: Aria", "reason": "user asked"},
    })
    kwargs = last_kwargs["update_personality"]
    assert kwargs["action"] == "propose"
    assert kwargs["proposed_soul"] == "name: Aria"
    assert kwargs["reason"] == "user asked"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_domain_action_returns_helpful_error(manage_with_stubs):
    manage, _ = manage_with_stubs
    result = await manage.ainvoke({"domain": "skill", "action": "frobnicate", "payload": {}})
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert "Unknown" in parsed["message"]
    # Error mentions at least one valid pair to help the LLM recover.
    assert "skill/" in parsed["message"]


@pytest.mark.asyncio
async def test_invalid_payload_returns_validation_error(manage_with_stubs):
    manage, _ = manage_with_stubs
    # skill.create requires name + description; sending only `name` should fail.
    result = await manage.ainvoke({"domain": "skill", "action": "create", "payload": {"name": "x"}})
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert "Invalid payload" in parsed["message"]


def test_build_manage_tool_returns_none_without_db_factory():
    assert build_manage_tool(_agent_ctx(), None) is None
