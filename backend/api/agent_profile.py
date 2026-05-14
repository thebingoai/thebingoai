"""
REST endpoints for the Agent Identity settings page.

GET  /api/agent-profile          -- fetch current user's orchestrator profile (draft state)
PATCH /api/agent-profile         -- save draft fields; auto-renders text columns
POST /api/agent-profile/publish  -- snapshot current state so agent uses it
POST /api/agent-profile/avatar   -- upload avatar image (stored as base64 data URL)
"""
import base64
import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.database.session import get_db
from backend.models.user import User

router = APIRouter(prefix="/agent-profile", tags=["agent-profile"])

_STRUCTURED_IDENTITY = {
    "display_name", "pronouns", "tagline", "default_model",
    "temperature", "max_output_tokens",
    "tone", "style_traits", "format_traits",
}
_STRUCTURED_CONTEXT  = {"user_profile", "user_narrative", "vocabulary", "sensitivities"}

# Fields a user can edit — the union of structured Identity, structured User Context,
# free-text sections, and rendered text columns. Used by both publish (to snapshot)
# and reset (to revert).
_EDITABLE_FIELDS = (
    # Identity
    "display_name", "pronouns", "tagline", "avatar_url",
    "default_model", "temperature", "max_output_tokens",
    "tone", "style_traits", "format_traits",
    # Free-text sections + rendered columns
    "soul", "identity", "user_context", "guardrails",
    # Soul attachments
    "style_references",
    # User context structured
    "user_profile", "user_narrative", "vocabulary", "sensitivities",
)


# -- Pydantic schemas ---------------------------------------------------------

class AgentProfilePatch(BaseModel):
    display_name:      Optional[str]                   = None
    pronouns:          Optional[str]                   = None
    tagline:           Optional[str]                   = None
    avatar_url:        Optional[str]                   = None
    default_model:     Optional[str]                   = None
    temperature:       Optional[float]                 = None
    max_output_tokens: Optional[int]                   = None
    tone:              Optional[float]                 = None
    style_traits:      Optional[List[str]]             = None
    format_traits:     Optional[List[str]]             = None
    soul:              Optional[str]                   = None
    style_references:  Optional[List[Dict[str, str]]]  = None
    user_profile:      Optional[Dict[str, Any]]        = None
    user_narrative:    Optional[str]                   = None
    vocabulary:        Optional[List[Dict[str, str]]]  = None
    sensitivities:     Optional[List[str]]             = None


class AgentProfileResponse(BaseModel):
    display_name:      Optional[str]
    pronouns:          Optional[str]
    tagline:           Optional[str]
    avatar_url:        Optional[str]
    default_model:     Optional[str]
    temperature:       Optional[float]
    max_output_tokens: Optional[int]
    tone:              Optional[float]
    style_traits:      Optional[List[str]]
    format_traits:     Optional[List[str]]
    soul:              Optional[str]
    style_references:  Optional[List[Dict[str, str]]]
    user_profile:      Optional[Dict[str, Any]]
    user_narrative:    Optional[str]
    vocabulary:        Optional[List[Dict[str, str]]]
    sensitivities:     Optional[List[str]]
    version:           int
    published_version: Optional[int]
    published_at:      Optional[str]
    published_soul:    Optional[str]
    published_avatar_url:  Optional[str]
    published_display_name: Optional[str]


# -- Helpers ------------------------------------------------------------------

def _get_or_seed_profile(db: Session, user_id: str):
    from backend.models.agent_profile import AgentProfile
    from backend.agents.profile_renderer import seed_default_profile

    profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == user_id,
        AgentProfile.agent_type == "orchestrator",
        AgentProfile.is_active.is_(True),
    ).first()

    if not profile:
        profile = seed_default_profile(db, user_id, "orchestrator")
        db.commit()

    return profile


def _to_response(profile) -> AgentProfileResponse:
    snapshot = profile.published_snapshot or {}
    return AgentProfileResponse(
        display_name=profile.display_name,
        pronouns=profile.pronouns,
        tagline=profile.tagline,
        avatar_url=profile.avatar_url,
        default_model=profile.default_model,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        tone=profile.tone,
        style_traits=profile.style_traits or [],
        format_traits=profile.format_traits or [],
        soul=profile.soul,
        style_references=profile.style_references or [],
        user_profile=profile.user_profile or {},
        user_narrative=profile.user_narrative,
        vocabulary=profile.vocabulary or [],
        sensitivities=profile.sensitivities or [],
        version=profile.version or 1,
        published_version=profile.published_version,
        published_at=str(profile.published_at) if profile.published_at else None,
        published_soul=snapshot.get('soul'),
        published_avatar_url=snapshot.get("avatar_url"),
        published_display_name=snapshot.get("display_name"),
    )


# -- Endpoints ----------------------------------------------------------------

@router.get("", response_model=AgentProfileResponse)
async def get_agent_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_seed_profile(db, user.id)
    return _to_response(profile)


@router.patch("", response_model=AgentProfileResponse)
async def patch_agent_profile(
    body: AgentProfilePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.services.agent_profile_renderer import render_identity_text, render_user_context_text

    profile = _get_or_seed_profile(db, user.id)
    patch_data = body.model_dump(exclude_unset=True)

    for field, value in patch_data.items():
        setattr(profile, field, value)

    # Bump version only on the FIRST edit after a publish.
    # While already in draft (version > published_version), keep the same version.
    # Pre-publish drafts stay at their seeded version.
    if profile.published_version is not None and profile.version == profile.published_version:
        profile.version = profile.published_version + 1

    if patch_data.keys() & _STRUCTURED_IDENTITY:
        profile.identity = render_identity_text(profile)
    if patch_data.keys() & _STRUCTURED_CONTEXT:
        profile.user_context = render_user_context_text(profile)

    db.commit()
    return _to_response(profile)


@router.post("/publish", response_model=AgentProfileResponse)
async def publish_agent_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_seed_profile(db, user.id)

    profile.published_snapshot = {f: getattr(profile, f) for f in _EDITABLE_FIELDS}
    profile.published_version = profile.version
    profile.published_at      = datetime.datetime.utcnow()

    db.commit()
    return _to_response(profile)


@router.post("/reset", response_model=AgentProfileResponse)
async def reset_agent_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Discard unpublished draft edits and revert to the last published snapshot."""
    profile = _get_or_seed_profile(db, user.id)

    if not profile.published_snapshot or profile.published_version is None:
        raise HTTPException(
            status_code=400,
            detail="Nothing to reset — no published version yet.",
        )

    for field in _EDITABLE_FIELDS:
        if field in profile.published_snapshot:
            setattr(profile, field, profile.published_snapshot[field])

    profile.version = profile.published_version

    db.commit()
    return _to_response(profile)


@router.post("/factory-reset", response_model=AgentProfileResponse)
async def factory_reset_agent_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Wipe every editable field back to the Bingo default and immediately
    publish the result, so chat behavior reverts in a single step."""
    from backend.agents.profile_defaults import get_default_section

    profile = _get_or_seed_profile(db, user.id)

    # Clear structured Identity + Identity-text-overlay
    profile.display_name      = None
    profile.pronouns          = None
    profile.tagline           = None
    profile.avatar_url        = None
    profile.default_model     = None
    profile.temperature       = None
    profile.max_output_tokens = None

    # Clear structured User Context
    profile.user_profile   = None
    profile.user_narrative = None
    profile.vocabulary     = None
    profile.sensitivities  = None

    # Restore rendered text sections from agent defaults
    profile.identity     = get_default_section("orchestrator", "identity") or ""
    profile.soul         = get_default_section("orchestrator", "soul")
    profile.user_context = get_default_section("orchestrator", "user_context")
    profile.guardrails   = get_default_section("orchestrator", "guardrails")

    # Publish the wiped state so chat reflects it immediately
    profile.version            = (profile.version or 1) + 1
    profile.published_snapshot = {f: getattr(profile, f) for f in _EDITABLE_FIELDS}
    profile.published_version  = profile.version
    profile.published_at       = datetime.datetime.utcnow()

    db.commit()
    return _to_response(profile)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported image type. Use PNG, JPEG, WEBP, or GIF.")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 2 MB).")

    data_url = f"data:{file.content_type};base64,{base64.b64encode(content).decode()}"

    profile = _get_or_seed_profile(db, user.id)
    profile.avatar_url = data_url
    profile.version    = (profile.version or 0) + 1
    db.commit()

    return {"avatar_url": data_url}


# -- Soul revision endpoint ---------------------------------------------------

class SoulReviseRequest(BaseModel):
    soul: str
    instruction: Optional[str] = None  # reserved for future use


class SoulReviseResponse(BaseModel):
    revised: str
    model: str


@router.post("/soul/revise", response_model=SoulReviseResponse)
async def revise_soul(
    body: SoulReviseRequest,
    user: User = Depends(get_current_user),
):
    """Ask the LLM to suggest a tightened revision of the soul prompt. Pure suggestion — does not write to DB."""
    from backend.config import settings
    from backend.llm.factory import get_provider

    if not body.soul.strip():
        raise HTTPException(status_code=400, detail="Soul text is required.")

    try:
        provider = get_provider(settings.default_llm_provider)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    messages = [
        {
            "role": "system",
            "content": (
                "You are an editor who tightens system prompts. "
                "Return ONLY the revised markdown, no preamble, no commentary, no surrounding fences. "
                "Preserve intent and concrete instructions; remove redundancy, hedging, and filler. "
                "Keep length similar or shorter."
            ),
        },
        {"role": "user", "content": body.soul},
    ]

    revised_text = await provider.chat(
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )

    return SoulReviseResponse(revised=revised_text.strip(), model=provider.get_default_model())
