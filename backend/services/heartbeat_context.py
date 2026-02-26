"""
Shared orchestrator context assembly for chat and heartbeat jobs.

Extracted from backend/api/chat.py so that Celery heartbeat tasks can
reuse the same context-building logic without duplicating it.
"""

from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.agents.context import AgentContext
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorInvocationContext:
    agent_context: AgentContext
    custom_agents: list = field(default_factory=list)
    memory_context: str = ""
    user_skills: list = field(default_factory=list)
    user_memories_context: str = ""


async def build_orchestrator_context(
    db: Session,
    user: User,
    query: str = "",
    connection_ids: Optional[list] = None,
    thread_id: Optional[str] = None,
) -> OrchestratorInvocationContext:
    """
    Build all context needed to invoke run_orchestrator / stream_orchestrator.

    Args:
        db: Database session
        user: Authenticated user
        query: The user's query (used for semantic memory search)
        connection_ids: Specific connection IDs to use. None = all user connections.
        thread_id: Optional thread ID for the agent context.

    Returns:
        OrchestratorInvocationContext with all assembled context.
    """
    # Resolve accessible connections
    if connection_ids:
        accessible_connections = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.id.in_(connection_ids),
            DatabaseConnection.user_id == user.id
        ).all()
        accessible_ids = [conn.id for conn in accessible_connections]
    else:
        accessible_connections = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.user_id == user.id
        ).all()
        accessible_ids = [conn.id for conn in accessible_connections]

    # Load team policies and custom agents
    from backend.services.policy_service import PolicyService
    from backend.models.custom_agent import CustomAgent as CustomAgentModel
    from backend.models.user_skill import UserSkill as UserSkillModel

    team_id = PolicyService.get_user_primary_team(db, user.id)
    allowed_tool_keys: list = []
    team_connection_ids: list = accessible_ids
    custom_agents = []

    if team_id:
        allowed_tool_keys = PolicyService.get_team_allowed_tools(db, team_id)
        team_allowed_connections = PolicyService.get_team_allowed_connections(db, team_id)
        if team_allowed_connections:
            team_connection_ids = [c for c in accessible_ids if c in team_allowed_connections]
        custom_agents = db.query(CustomAgentModel).filter(
            CustomAgentModel.user_id == user.id,
            CustomAgentModel.team_id == team_id,
            CustomAgentModel.is_active == True,
        ).all()

    # Load user's active skills
    user_skills = db.query(UserSkillModel).filter(
        UserSkillModel.user_id == user.id,
        UserSkillModel.is_active == True,
    ).all()

    # Build AgentContext
    agent_context = AgentContext(
        user_id=user.id,
        available_connections=team_connection_ids,
        thread_id=thread_id,
        team_id=team_id,
        allowed_tool_keys=allowed_tool_keys,
    )

    # Check if auto-memory retrieval is enabled
    prefs = user.preferences or {}
    memory_enabled = prefs.get("memory_enabled", True)

    # Pre-fetch auto-generated memory context (Qdrant)
    memory_context = ""
    if memory_enabled and query:
        try:
            from backend.memory.retriever import MemoryRetriever
            retriever = MemoryRetriever()
            memory_context = await retriever.get_relevant_context(
                user_id=user.id, query=query, top_k=3
            )
        except Exception as mem_err:
            logger.warning(f"Memory retrieval failed: {mem_err}")

    # Load user-directed memories (PostgreSQL)
    from backend.models.user_memory import UserMemory as UserMemoryModel
    user_memory_entries = db.query(UserMemoryModel).filter(
        UserMemoryModel.user_id == user.id,
        UserMemoryModel.is_active == True,
    ).all()
    user_memories_context = ""
    if user_memory_entries:
        lines = "\n".join(f"- {m.content}" for m in user_memory_entries)
        user_memories_context = lines

    return OrchestratorInvocationContext(
        agent_context=agent_context,
        custom_agents=custom_agents,
        memory_context=memory_context,
        user_skills=user_skills,
        user_memories_context=user_memories_context,
    )
