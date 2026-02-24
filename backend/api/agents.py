from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.custom_agent import CustomAgent
from backend.models.team_membership import TeamMembership
from backend.services.policy_service import PolicyService
import uuid

router = APIRouter(prefix="/agents", tags=["custom-agents"])


class AgentCreate(BaseModel):
    team_id: str
    name: str
    description: Optional[str] = None
    system_prompt: str
    tool_keys: List[str]
    connection_ids: Optional[List[int]] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    tool_keys: Optional[List[str]] = None
    connection_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class AgentResponse(BaseModel):
    id: str
    user_id: str
    team_id: str
    name: str
    description: Optional[str]
    system_prompt: str
    tool_keys: List[str]
    connection_ids: Optional[List[int]]
    is_active: bool
    created_at: str
    updated_at: str


class EffectiveToolsResponse(BaseModel):
    agent_id: str
    effective_tool_keys: List[str]
    effective_connection_ids: List[int]
    filtered_tools: List[str]       # tools removed by team policy
    filtered_connections: List[int] # connections removed by team policy


def _agent_to_response(agent: CustomAgent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        user_id=agent.user_id,
        team_id=agent.team_id,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        tool_keys=agent.tool_keys or [],
        connection_ids=agent.connection_ids,
        is_active=agent.is_active,
        created_at=str(agent.created_at),
        updated_at=str(agent.updated_at),
    )


def _validate_membership(db: Session, user_id: str, team_id: str):
    """Raise 403 if user is not a member of the team."""
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this team")


def _validate_tools_and_connections(db: Session, team_id: str, tool_keys: List[str], connection_ids: Optional[List[int]]):
    """Validate tool_keys and connection_ids against team policy, raising 400 on violation."""
    valid, violations = PolicyService.validate_agent_tools(db, team_id, tool_keys)
    if not valid:
        raise HTTPException(
            status_code=400,
            detail=f"Tool(s) not allowed by team policy: {', '.join(violations)}",
        )

    if connection_ids:
        valid_conn, violations_conn = PolicyService.validate_agent_connections(db, team_id, connection_ids)
        if not valid_conn:
            raise HTTPException(
                status_code=400,
                detail=f"Connection ID(s) not allowed by team policy: {violations_conn}",
            )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a custom agent for the current user within a team."""
    _validate_membership(db, current_user.id, payload.team_id)
    _validate_tools_and_connections(db, payload.team_id, payload.tool_keys, payload.connection_ids)

    agent = CustomAgent(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        team_id=payload.team_id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        tool_keys=payload.tool_keys,
        connection_ids=payload.connection_ids,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _agent_to_response(agent)


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all custom agents owned by the current user."""
    agents = db.query(CustomAgent).filter(
        CustomAgent.user_id == current_user.id,
        CustomAgent.is_active == True,
    ).all()
    return [_agent_to_response(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific custom agent."""
    agent = db.query(CustomAgent).filter(
        CustomAgent.id == agent_id,
        CustomAgent.user_id == current_user.id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _agent_to_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a custom agent."""
    agent = db.query(CustomAgent).filter(
        CustomAgent.id == agent_id,
        CustomAgent.user_id == current_user.id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Determine the final tool_keys and connection_ids for validation
    final_tools = payload.tool_keys if payload.tool_keys is not None else agent.tool_keys
    final_connections = payload.connection_ids if payload.connection_ids is not None else agent.connection_ids

    _validate_tools_and_connections(db, agent.team_id, final_tools, final_connections)

    if payload.name is not None:
        agent.name = payload.name
    if payload.description is not None:
        agent.description = payload.description
    if payload.system_prompt is not None:
        agent.system_prompt = payload.system_prompt
    if payload.tool_keys is not None:
        agent.tool_keys = payload.tool_keys
    if payload.connection_ids is not None:
        agent.connection_ids = payload.connection_ids
    if payload.is_active is not None:
        agent.is_active = payload.is_active

    db.commit()
    db.refresh(agent)
    return _agent_to_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a custom agent."""
    agent = db.query(CustomAgent).filter(
        CustomAgent.id == agent_id,
        CustomAgent.user_id == current_user.id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.is_active = False
    db.commit()


@router.get("/{agent_id}/effective-tools", response_model=EffectiveToolsResponse)
async def get_effective_tools(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Preview the effective tool set and connections this agent would have at runtime.

    Applies the current team policy intersection against the agent's stored tool_keys
    and connection_ids — shows what would actually be available if invoked now.
    """
    agent = db.query(CustomAgent).filter(
        CustomAgent.id == agent_id,
        CustomAgent.user_id == current_user.id,
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    allowed_tools = set(PolicyService.get_team_allowed_tools(db, agent.team_id))
    allowed_connections = set(PolicyService.get_team_allowed_connections(db, agent.team_id))

    agent_tools = agent.tool_keys or []
    agent_connections = agent.connection_ids or []

    effective_tools = [t for t in agent_tools if t in allowed_tools]
    effective_connections = [c for c in agent_connections if c in allowed_connections]
    filtered_tools = [t for t in agent_tools if t not in allowed_tools]
    filtered_connections = [c for c in agent_connections if c not in allowed_connections]

    return EffectiveToolsResponse(
        agent_id=agent_id,
        effective_tool_keys=effective_tools,
        effective_connection_ids=effective_connections,
        filtered_tools=filtered_tools,
        filtered_connections=filtered_connections,
    )
