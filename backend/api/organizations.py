from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.organization import Organization
from backend.models.team import Team
import uuid

router = APIRouter(prefix="/orgs", tags=["organizations"])


class OrgCreate(BaseModel):
    name: str


class OrgResponse(BaseModel):
    id: str
    name: str
    created_at: str

    class Config:
        from_attributes = True


class TeamCreate(BaseModel):
    name: str


class TeamResponse(BaseModel):
    id: str
    org_id: str
    name: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    payload: OrgCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new organization (super-admin only — for now any authenticated user)."""
    existing = db.query(Organization).filter(Organization.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Organization name already taken")

    org = Organization(id=str(uuid.uuid4()), name=payload.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrgResponse(id=org.id, name=org.name, created_at=str(org.created_at))


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get organization details."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrgResponse(id=org.id, name=org.name, created_at=str(org.created_at))


@router.post("/{org_id}/teams", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    org_id: str,
    payload: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a team within an organization."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = db.query(Team).filter(Team.org_id == org_id, Team.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Team name already exists in this organization")

    team = Team(id=str(uuid.uuid4()), org_id=org_id, name=payload.name)
    db.add(team)
    db.commit()
    db.refresh(team)
    return TeamResponse(id=team.id, org_id=team.org_id, name=team.name, created_at=str(team.created_at))


@router.get("/{org_id}/teams", response_model=List[TeamResponse])
async def list_teams(
    org_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all teams in an organization."""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    teams = db.query(Team).filter(Team.org_id == org_id).all()
    return [
        TeamResponse(id=t.id, org_id=t.org_id, name=t.name, created_at=str(t.created_at))
        for t in teams
    ]
