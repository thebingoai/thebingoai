"""
API endpoints for agent session management.

All endpoints are user-scoped — authenticated users can only see and manage
their own agent sessions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.config import settings

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-sessions", tags=["agent-sessions"])


@router.get("")
async def list_sessions(
    agent_type: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """List all active agent sessions for the authenticated user."""
    if not settings.agent_mesh_enabled:
        return {"sessions": [], "mesh_enabled": False}

    from backend.services.agent_discovery import AgentDiscovery

    discovery = AgentDiscovery()
    sessions = discovery.list_sessions(user.id, filter_type=agent_type)

    return {
        "sessions": [
            {
                "session_id": s.get("session_id"),
                "agent_type": s.get("agent_type"),
                "status": s.get("status"),
                "capabilities": s.get("capabilities", {}),
                "last_heartbeat": s.get("last_heartbeat"),
            }
            for s in sessions
        ],
        "mesh_enabled": True,
    }


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """Get details for a specific agent session."""
    if not settings.agent_mesh_enabled:
        raise HTTPException(status_code=404, detail="Agent mesh not enabled")

    from backend.services.agent_discovery import AgentDiscovery

    discovery = AgentDiscovery()
    try:
        session = discovery.get_session(user.id, session_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your session")
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.get("/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get message history for a specific agent session."""
    if not settings.agent_mesh_enabled:
        raise HTTPException(status_code=404, detail="Agent mesh not enabled")

    from backend.services.agent_discovery import AgentDiscovery
    from backend.services.agent_message_bus import AgentMessageBus

    # Validate ownership
    discovery = AgentDiscovery()
    try:
        discovery.get_session(user.id, session_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your session")
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")

    bus = AgentMessageBus(db_session=db)
    messages = bus.get_history(user.id, session_id, limit=limit)

    return {"messages": messages}


@router.post("/{session_id}/send")
async def send_message(
    session_id: str,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send a message to an agent session."""
    if not settings.agent_mesh_enabled:
        raise HTTPException(status_code=404, detail="Agent mesh not enabled")

    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    from_session_id = body.get("from_session_id")
    if not from_session_id:
        raise HTTPException(status_code=400, detail="from_session_id is required")

    from backend.services.agent_message_bus import AgentMessageBus

    bus = AgentMessageBus(db_session=db)
    try:
        msg_id = bus.send(
            user_id=user.id,
            from_session_id=from_session_id,
            to_session_id=session_id,
            content={"text": message},
            message_type="request",
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"message_id": msg_id, "status": "sent"}


@router.delete("/{session_id}")
async def terminate_session(
    session_id: str,
    user: User = Depends(get_current_user),
):
    """Terminate an agent session."""
    if not settings.agent_mesh_enabled:
        raise HTTPException(status_code=404, detail="Agent mesh not enabled")

    from backend.services.agent_registry import AgentRegistry

    registry = AgentRegistry()
    try:
        registry.deregister_session(user.id, session_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your session")

    return {"status": "terminated"}
