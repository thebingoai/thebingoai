"""
manage_tool.py — Single meta-tool that dispatches admin operations across
domains (skill, profile, soul, connection) to the existing tool implementations.

Reduces the orchestrator's bound-tool surface by collapsing ~10 admin tools into
one. The LLM picks (domain, action) and supplies a typed payload; this module
validates the payload via Pydantic, then forwards to the underlying tool by
name.

Underlying tools are reused as-is — no business logic moves here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Literal, Optional

from langchain_core.tools import tool, BaseTool
from pydantic import BaseModel, Field, ValidationError

from backend.agents.context import AgentContext
from backend.agents.orchestrator.skill_tools import build_skill_tools
from backend.agents.orchestrator.profile_tools import build_profile_tools
from backend.agents.orchestrator.soul_tools import build_soul_tools
from backend.agents.orchestrator.orchestrator_dashboard_tools import build_dashboard_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM-facing schema
# ---------------------------------------------------------------------------

Domain = Literal["skill", "profile", "soul", "connection", "dashboard"]


class ManageRequest(BaseModel):
    """Single admin meta-request. Pick (domain, action), supply matching payload."""

    domain: Domain = Field(..., description="Admin domain.")
    action: str = Field(
        ...,
        description=(
            "Action within the domain. Valid pairs: "
            "skill[create|update|delete|get|list|use|suggestion], "
            "profile[read|write], soul[propose|apply], connection[list]."
        ),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Payload fields for this (domain, action). See validators.",
    )


# ---------------------------------------------------------------------------
# Per-(domain, action) payload schemas
# ---------------------------------------------------------------------------

class _SkillCreate(BaseModel):
    name: str
    description: str
    instructions: str = ""
    prompt_template: str = ""
    code: str = ""
    parameters_schema: str = ""
    secrets: str = ""
    activation_hint: str = ""
    references: str = ""


class _SkillUpdate(BaseModel):
    skill_name: str
    description: str = ""
    instructions: str = ""
    prompt_template: str = ""
    code: str = ""
    parameters_schema: str = ""
    activation_hint: str = ""
    add_references: str = ""
    remove_reference_titles: str = ""


class _SkillDelete(BaseModel):
    skill_name: str


class _SkillGet(BaseModel):
    name: str
    reference_title: str = ""


class _SkillList(BaseModel):
    pass


class _SkillUse(BaseModel):
    skill_name: str
    params: dict[str, Any] = Field(default_factory=dict)


class _SkillSuggestion(BaseModel):
    decision: Literal["check", "accept", "dismiss"]
    suggestion_id: str = ""


class _ProfileRead(BaseModel):
    section: str = ""


class _ProfileWrite(BaseModel):
    section: str
    content: str


class _SoulPropose(BaseModel):
    proposed_soul: str
    reason: str = ""


class _SoulApply(BaseModel):
    proposed_soul: str


class _ConnectionList(BaseModel):
    pass


# (domain, action) → (payload schema, underlying tool name, kwargs builder)
_DispatchSpec = tuple[type[BaseModel], str, Callable[[BaseModel], dict[str, Any]]]


def _skill_create_kwargs(p: _SkillCreate) -> dict[str, Any]:
    return {"action": "create", **p.model_dump()}


def _skill_update_kwargs(p: _SkillUpdate) -> dict[str, Any]:
    return {"action": "update", **p.model_dump()}


def _skill_delete_kwargs(p: _SkillDelete) -> dict[str, Any]:
    return {"action": "delete", "skill_name": p.skill_name}


def _skill_use_kwargs(p: _SkillUse) -> dict[str, Any]:
    return {"skill_name": p.skill_name, "params_json": json.dumps(p.params or {})}


def _skill_suggestion_kwargs(p: _SkillSuggestion) -> dict[str, Any]:
    return {"action": p.decision, "suggestion_id": p.suggestion_id}


def _soul_propose_kwargs(p: _SoulPropose) -> dict[str, Any]:
    return {"action": "propose", "proposed_soul": p.proposed_soul, "reason": p.reason}


def _soul_apply_kwargs(p: _SoulApply) -> dict[str, Any]:
    return {"action": "apply", "proposed_soul": p.proposed_soul}


class _DashboardList(BaseModel):
    pass


_DISPATCH: dict[tuple[str, str], _DispatchSpec] = {
    ("skill", "create"):     (_SkillCreate, "manage_skill", _skill_create_kwargs),
    ("skill", "update"):     (_SkillUpdate, "manage_skill", _skill_update_kwargs),
    ("skill", "delete"):     (_SkillDelete, "manage_skill", _skill_delete_kwargs),
    ("skill", "get"):        (_SkillGet,    "get_skill",    lambda p: p.model_dump()),
    ("skill", "list"):       (_SkillList,   "list_skills",  lambda _: {}),
    ("skill", "use"):        (_SkillUse,    "use_skill",    _skill_use_kwargs),
    ("skill", "suggestion"): (_SkillSuggestion, "handle_suggestion", _skill_suggestion_kwargs),
    ("profile", "read"):     (_ProfileRead, "read_profile", lambda p: p.model_dump()),
    ("profile", "write"):    (_ProfileWrite, "write_profile", lambda p: p.model_dump()),
    ("soul", "propose"):     (_SoulPropose, "update_personality", _soul_propose_kwargs),
    ("soul", "apply"):       (_SoulApply,   "update_personality", _soul_apply_kwargs),
    ("connection", "list"):  (_ConnectionList, "list_connections", lambda _: {}),
    ("dashboard", "list"):   (_DashboardList, "list_dashboards", lambda _: {}),
}


_TOOL_DESCRIPTION = """Admin operations across skills, profile, soul, connections, and dashboard listing.

Pick a (domain, action) pair and supply the matching `payload`. Invalid pairs
return an error. Do NOT use this tool for data queries, the dashboard verbs
(create/update/read/analyze), knowledge retrieval, memory, or running custom
agents — those have dedicated primary tools.

Valid pairs and their payload fields:

  skill, create      payload: {name, description, instructions?, code?, prompt_template?,
                               parameters_schema? (JSON str), secrets? (JSON str),
                               activation_hint?, references? (JSON array str)}
  skill, update      payload: {skill_name, description?, instructions?, code?,
                               prompt_template?, parameters_schema?, activation_hint?,
                               add_references? (JSON array str),
                               remove_reference_titles? (JSON array str)}
  skill, delete      payload: {skill_name}
  skill, get         payload: {name, reference_title?}
  skill, list        payload: {}
  skill, use         payload: {skill_name, params: object}
  skill, suggestion  payload: {decision: "check"|"accept"|"dismiss", suggestion_id?}
  profile, read      payload: {section?}
  profile, write     payload: {section, content}
  soul, propose      payload: {proposed_soul, reason?}
  soul, apply        payload: {proposed_soul}
  connection, list   payload: {}
  dashboard, list    payload: {}
"""


def build_manage_tool(
    context: AgentContext,
    db_session_factory: Optional[Callable] = None,
) -> Optional[BaseTool]:
    """Build the `manage` meta-tool. Returns None when no db session factory is
    provided (matches the existing skill/profile/soul tool builders, which all
    return empty lists in that case)."""
    if db_session_factory is None:
        return None

    skill_tools = build_skill_tools(context, db_session_factory)
    profile_tools_list = build_profile_tools(context, db_session_factory)
    soul_tools = build_soul_tools(context, db_session_factory)
    dashboard_tools = build_dashboard_tools(context, db_session_factory)

    by_name: dict[str, BaseTool] = {}
    for t in (*skill_tools, *profile_tools_list, *soul_tools, *dashboard_tools):
        by_name[t.name] = t

    @tool("manage", description=_TOOL_DESCRIPTION, args_schema=ManageRequest)
    async def manage(domain: str, action: str, payload: Optional[dict[str, Any]] = None) -> str:
        key = (domain, action)
        spec = _DISPATCH.get(key)
        if spec is None:
            valid = ", ".join(f"{d}/{a}" for d, a in _DISPATCH)
            return json.dumps({
                "success": False,
                "message": f"Unknown (domain, action): ({domain}, {action}). Valid: {valid}",
            })

        schema_cls, tool_name, kwargs_fn = spec
        try:
            typed = schema_cls(**(payload or {}))
        except ValidationError as exc:
            return json.dumps({
                "success": False,
                "message": f"Invalid payload for ({domain}, {action}): {exc.errors()}",
            })

        underlying = by_name.get(tool_name)
        if underlying is None:
            logger.error("manage: underlying tool '%s' not registered", tool_name)
            return json.dumps({
                "success": False,
                "message": f"Underlying tool '{tool_name}' is unavailable in this context.",
            })

        kwargs = kwargs_fn(typed)
        try:
            result = await underlying.ainvoke(kwargs)
        except Exception as exc:
            logger.error("manage(%s, %s) dispatch failed: %s", domain, action, exc)
            return json.dumps({"success": False, "message": str(exc)})

        # Underlying tools all return JSON strings already. Pass through.
        if isinstance(result, str):
            return result
        try:
            return json.dumps(result)
        except (TypeError, ValueError):
            return str(result)

    return manage
