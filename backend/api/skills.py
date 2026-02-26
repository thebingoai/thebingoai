from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.user_skill import UserSkill
from backend.models.skill_reference import SkillReference
from backend.models.skill_suggestion import SkillSuggestion
from backend.schemas.skill import (
    SkillResponse,
    SkillDetailResponse,
    SkillReferenceResponse,
    SkillToggleRequest,
    SkillSuggestionResponse,
    SkillSuggestionRespondRequest,
)
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


def _to_response(s: UserSkill) -> SkillResponse:
    return SkillResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        skill_type=s.skill_type or "code",
        has_prompt_template=bool(s.prompt_template),
        has_code=bool(s.code),
        has_instructions=bool(s.instructions),
        reference_count=len(s.references) if s.references is not None else 0,
        version=s.version or 1,
        parameters_schema=s.parameters_schema,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def _to_detail_response(s: UserSkill) -> SkillDetailResponse:
    return SkillDetailResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        skill_type=s.skill_type or "code",
        has_prompt_template=bool(s.prompt_template),
        has_code=bool(s.code),
        has_instructions=bool(s.instructions),
        reference_count=len(s.references) if s.references is not None else 0,
        version=s.version or 1,
        parameters_schema=s.parameters_schema,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
        instructions=s.instructions,
        prompt_template=s.prompt_template,
        activation_hint=s.activation_hint,
        references=[
            SkillReferenceResponse(
                id=r.id,
                title=r.title,
                sort_order=r.sort_order,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in sorted(s.references, key=lambda r: r.sort_order)
        ] if s.references else [],
    )


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all skills for the current user."""
    skills = db.query(UserSkill).options(joinedload(UserSkill.references)).filter(
        UserSkill.user_id == current_user.id
    ).order_by(UserSkill.created_at.desc()).all()

    return [_to_response(s) for s in skills]


@router.get("/suggestions", response_model=List[SkillSuggestionResponse])
async def list_suggestions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List pending skill suggestions for the current user."""
    suggestions = db.query(SkillSuggestion).filter(
        SkillSuggestion.user_id == current_user.id,
        SkillSuggestion.status == "pending",
    ).order_by(SkillSuggestion.confidence.desc()).all()

    return [
        SkillSuggestionResponse(
            id=s.id,
            suggested_name=s.suggested_name,
            suggested_description=s.suggested_description,
            suggested_skill_type=s.suggested_skill_type,
            pattern_summary=s.pattern_summary,
            confidence=s.confidence,
            status=s.status,
            created_at=s.created_at,
        )
        for s in suggestions
    ]


@router.get("/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full skill details including instructions and references."""
    skill = db.query(UserSkill).options(joinedload(UserSkill.references)).filter(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return _to_detail_response(skill)


@router.get("/{skill_id}/references", response_model=List[SkillReferenceResponse])
async def list_skill_references(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List reference titles for a skill."""
    skill = db.query(UserSkill).filter(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    refs = db.query(SkillReference).filter(
        SkillReference.skill_id == skill_id
    ).order_by(SkillReference.sort_order).all()

    return [
        SkillReferenceResponse(
            id=r.id,
            title=r.title,
            sort_order=r.sort_order,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in refs
    ]


@router.patch("/{skill_id}", response_model=SkillResponse)
async def toggle_skill(
    skill_id: str,
    request: SkillToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle a skill's active state."""
    skill = db.query(UserSkill).options(joinedload(UserSkill.references)).filter(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    skill.is_active = request.is_active
    db.commit()
    db.refresh(skill)

    return _to_response(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a skill."""
    skill = db.query(UserSkill).filter(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    ).first()

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    db.delete(skill)
    db.commit()


@router.patch("/suggestions/{suggestion_id}", response_model=SkillSuggestionResponse)
async def respond_to_suggestion(
    suggestion_id: str,
    request: SkillSuggestionRespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept or dismiss a skill suggestion."""
    if request.action not in ("accept", "dismiss"):
        raise HTTPException(status_code=400, detail="action must be 'accept' or 'dismiss'")

    suggestion = db.query(SkillSuggestion).filter(
        SkillSuggestion.id == suggestion_id,
        SkillSuggestion.user_id == current_user.id,
    ).first()

    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if request.action == "accept":
        # Create the skill from the suggestion
        new_skill = UserSkill(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            name=suggestion.suggested_name,
            description=suggestion.suggested_description or "",
            skill_type=suggestion.suggested_skill_type or "instruction",
            instructions=suggestion.suggested_instructions,
            is_active=True,
            version=1,
        )
        db.add(new_skill)
        suggestion.status = "accepted"
    else:
        suggestion.status = "dismissed"

    db.commit()
    db.refresh(suggestion)

    return SkillSuggestionResponse(
        id=suggestion.id,
        suggested_name=suggestion.suggested_name,
        suggested_description=suggestion.suggested_description,
        suggested_skill_type=suggestion.suggested_skill_type,
        pattern_summary=suggestion.pattern_summary,
        confidence=suggestion.confidence,
        status=suggestion.status,
        created_at=suggestion.created_at,
    )
