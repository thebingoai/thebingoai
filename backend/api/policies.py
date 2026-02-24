from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.team import Team
from backend.models.tool_catalog import ToolCatalog
from backend.models.team_tool_policy import TeamToolPolicy
from backend.models.team_connection_policy import TeamConnectionPolicy
import uuid

router = APIRouter(prefix="/tools", tags=["policies"])


# ---- Tool catalog ----

class ToolCatalogResponse(BaseModel):
    id: str
    tool_key: str
    display_name: str
    description: str | None
    category: str
    is_system: bool


@router.get("/catalog", response_model=List[ToolCatalogResponse])
async def list_tool_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all tools available in the platform catalog."""
    tools = db.query(ToolCatalog).all()
    return [
        ToolCatalogResponse(
            id=t.id,
            tool_key=t.tool_key,
            display_name=t.display_name,
            description=t.description,
            category=t.category.value,
            is_system=t.is_system,
        )
        for t in tools
    ]


# ---- Team tool policies ----

class TeamToolPolicySet(BaseModel):
    tool_keys: List[str]


class TeamToolPolicyResponse(BaseModel):
    team_id: str
    tool_keys: List[str]


@router.get("/teams/{team_id}/policies/tools", response_model=TeamToolPolicyResponse)
async def get_team_tool_policy(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the tool whitelist for a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    rows = db.query(TeamToolPolicy).filter(
        TeamToolPolicy.team_id == team_id,
        TeamToolPolicy.is_enabled == True,
    ).all()
    return TeamToolPolicyResponse(team_id=team_id, tool_keys=[r.tool_key for r in rows])


@router.put("/teams/{team_id}/policies/tools", response_model=TeamToolPolicyResponse)
async def set_team_tool_policy(
    team_id: str,
    payload: TeamToolPolicySet,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the tool whitelist for a team (replaces existing policy)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Validate all requested tool_keys exist in the catalog
    catalog_keys = {t.tool_key for t in db.query(ToolCatalog).all()}
    invalid = [k for k in payload.tool_keys if k not in catalog_keys]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tool_key(s): {', '.join(invalid)}. Check GET /api/tools/catalog.",
        )

    # Remove existing policies, then recreate
    db.query(TeamToolPolicy).filter(TeamToolPolicy.team_id == team_id).delete()
    for key in payload.tool_keys:
        db.add(TeamToolPolicy(id=str(uuid.uuid4()), team_id=team_id, tool_key=key))
    db.commit()

    return TeamToolPolicyResponse(team_id=team_id, tool_keys=payload.tool_keys)


# ---- Team connection policies ----

class TeamConnectionPolicySet(BaseModel):
    connection_ids: List[int]


class TeamConnectionPolicyResponse(BaseModel):
    team_id: str
    connection_ids: List[int]


@router.get("/teams/{team_id}/policies/connections", response_model=TeamConnectionPolicyResponse)
async def get_team_connection_policy(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the database connection whitelist for a team."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    rows = db.query(TeamConnectionPolicy).filter(
        TeamConnectionPolicy.team_id == team_id,
        TeamConnectionPolicy.is_enabled == True,
    ).all()
    return TeamConnectionPolicyResponse(team_id=team_id, connection_ids=[r.connection_id for r in rows])


@router.put("/teams/{team_id}/policies/connections", response_model=TeamConnectionPolicyResponse)
async def set_team_connection_policy(
    team_id: str,
    payload: TeamConnectionPolicySet,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set the database connection whitelist for a team (replaces existing policy)."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    db.query(TeamConnectionPolicy).filter(TeamConnectionPolicy.team_id == team_id).delete()
    for conn_id in payload.connection_ids:
        db.add(TeamConnectionPolicy(
            id=str(uuid.uuid4()),
            team_id=team_id,
            connection_id=conn_id,
        ))
    db.commit()

    return TeamConnectionPolicyResponse(team_id=team_id, connection_ids=payload.connection_ids)
