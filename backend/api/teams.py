from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.team import Team
from backend.models.team_membership import TeamMembership, MemberRole
import uuid

router = APIRouter(prefix="/teams", tags=["teams"])


class MemberAdd(BaseModel):
    user_id: str
    role: MemberRole = MemberRole.MEMBER


class MemberRoleUpdate(BaseModel):
    role: MemberRole


class MembershipResponse(BaseModel):
    id: str
    user_id: str
    team_id: str
    role: str
    created_at: str

    class Config:
        from_attributes = True


class MemberDetailResponse(BaseModel):
    id: str
    user_id: str
    user_email: str
    team_id: str
    role: str
    created_at: str


@router.get("/{team_id}/members", response_model=List[MemberDetailResponse])
async def list_members(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all members of a team with their email addresses."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    memberships = (
        db.query(TeamMembership, User)
        .join(User, TeamMembership.user_id == User.id)
        .filter(TeamMembership.team_id == team_id)
        .all()
    )
    return [
        MemberDetailResponse(
            id=m.id,
            user_id=m.user_id,
            user_email=u.email,
            team_id=m.team_id,
            role=m.role.value,
            created_at=str(m.created_at),
        )
        for m, u in memberships
    ]


@router.post("/{team_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    team_id: str,
    payload: MemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a user to a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    existing = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == payload.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member of this team")

    membership = TeamMembership(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        team_id=team_id,
        role=payload.role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        team_id=membership.team_id,
        role=membership.role.value,
        created_at=str(membership.created_at),
    )


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a user from a team."""
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    db.delete(membership)
    db.commit()


@router.patch("/{team_id}/members/{user_id}", response_model=MembershipResponse)
async def update_member_role(
    team_id: str,
    user_id: str,
    payload: MemberRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a member's role in a team."""
    membership = db.query(TeamMembership).filter(
        TeamMembership.team_id == team_id,
        TeamMembership.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")

    membership.role = payload.role
    db.commit()
    db.refresh(membership)
    return MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        team_id=membership.team_id,
        role=membership.role.value,
        created_at=str(membership.created_at),
    )
