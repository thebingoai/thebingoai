from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.user_skill import UserSkill
from backend.schemas.skill import SkillResponse, SkillToggleRequest
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


def _to_response(s: UserSkill) -> SkillResponse:
    return SkillResponse(
        id=s.id,
        name=s.name,
        description=s.description,
        has_prompt_template=bool(s.prompt_template),
        has_code=bool(s.code),
        parameters_schema=s.parameters_schema,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=List[SkillResponse])
async def list_skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all skills for the current user."""
    skills = db.query(UserSkill).filter(
        UserSkill.user_id == current_user.id
    ).order_by(UserSkill.created_at.desc()).all()

    return [_to_response(s) for s in skills]


@router.patch("/{skill_id}", response_model=SkillResponse)
async def toggle_skill(
    skill_id: str,
    request: SkillToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle a skill's active state."""
    skill = db.query(UserSkill).filter(
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
