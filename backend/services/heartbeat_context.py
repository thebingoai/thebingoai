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
from backend.agents.context import AgentContext, ConnectionInfo
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorInvocationContext:
    agent_context: AgentContext
    profile: object = None  # AgentProfile — loaded from DB or default
    custom_agents: list = field(default_factory=list)
    memory_context: str = ""
    user_skills: list = field(default_factory=list)
    user_memories_context: str = ""
    skill_suggestions: list = field(default_factory=list)
    soul_prompt: str = ""  # Kept for backward compat, prefer profile.soul


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
    # Resolve accessible connections (with metadata for agent prompts)
    conn_columns = (
        DatabaseConnection.id, DatabaseConnection.name,
        DatabaseConnection.db_type, DatabaseConnection.database,
    )
    if connection_ids:
        accessible_connections = db.query(*conn_columns).filter(
            DatabaseConnection.id.in_(connection_ids),
            DatabaseConnection.user_id == user.id
        ).all()
    else:
        accessible_connections = db.query(*conn_columns).filter(
            DatabaseConnection.user_id == user.id
        ).all()
    accessible_ids = [c.id for c in accessible_connections]
    connection_metadata = [
        ConnectionInfo(id=c.id, name=c.name, db_type=c.db_type, database=c.database)
        for c in accessible_connections
    ]

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
    from backend.models.skill_suggestion import SkillSuggestion as SkillSuggestionModel

    user_skills = db.query(UserSkillModel).filter(
        UserSkillModel.user_id == user.id,
        UserSkillModel.is_active == True,
    ).all()

    # Load pending skill suggestions (limit 3 for prompt injection)
    raw_suggestions = db.query(SkillSuggestionModel).filter(
        SkillSuggestionModel.user_id == user.id,
        SkillSuggestionModel.status == "pending",
    ).order_by(SkillSuggestionModel.confidence.desc()).limit(3).all()

    skill_suggestions = [
        {
            "id": s.id,
            "suggested_name": s.suggested_name,
            "pattern_summary": s.pattern_summary,
            "confidence": s.confidence,
        }
        for s in raw_suggestions
    ]

    # Build AgentContext
    # Filter metadata to match team-restricted connections
    team_meta = [m for m in connection_metadata if m.id in team_connection_ids]
    agent_context = AgentContext(
        user_id=user.id,
        available_connections=team_connection_ids,
        connection_metadata=team_meta,
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

    # Auto-provision agent mesh sessions when enabled
    from backend.config import settings as _settings

    if _settings.agent_mesh_enabled:
        try:
            session_id = await _ensure_mesh_sessions(user.id, agent_context)
            agent_context.session_id = session_id
        except Exception as mesh_err:
            logger.warning(f"Agent mesh session provisioning failed: {mesh_err}")

    # Load or lazy-seed the orchestrator's AgentProfile
    from backend.models.agent_profile import AgentProfile
    from backend.agents.profile_renderer import ProfileRenderer, seed_default_profile

    profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == user.id,
        AgentProfile.agent_type == "orchestrator",
        AgentProfile.is_active.is_(True),
    ).first()

    logger.info("AgentProfile loaded: %s (version=%s)", profile.id if profile else "NONE", profile.version if profile else "-")

    if not profile:
        profile = seed_default_profile(
            db, user.id, "orchestrator",
            org_id=getattr(user, "org_id", None),
            team_id=team_id,
        )
        db.commit()

    fresh_user = db.query(User).filter(User.id == user.id).first()
    # Sync soul_prompt: prefer profile.soul, fall back to User.soul_prompt for migration
    soul = profile.soul if profile.soul else ((fresh_user.soul_prompt if fresh_user else None) or "")

    logger.info("heartbeat_context returning: profile=%s, profile.id=%s", profile, getattr(profile, 'id', 'N/A'))
    result = OrchestratorInvocationContext(
        agent_context=agent_context,
        profile=profile,
        custom_agents=custom_agents,
        memory_context=memory_context,
        user_skills=user_skills,
        user_memories_context=user_memories_context,
        skill_suggestions=skill_suggestions,
        soul_prompt=soul,
    )
    logger.info("heartbeat_context result.profile=%s", result.profile)
    return result


async def _ensure_mesh_sessions(user_id: str, context: AgentContext) -> str:
    """
    Ensure built-in agent sessions exist for the user.

    Creates sessions for orchestrator, data_agent, dashboard_agent, rag_agent
    if they don't already exist. Returns the orchestrator's session_id.
    """
    import uuid
    from backend.services.agent_registry import AgentRegistry
    from backend.services.agent_discovery import AgentDiscovery

    registry = AgentRegistry()
    discovery = AgentDiscovery(redis_client=registry.redis)

    built_in_types = ["orchestrator", "data_agent", "dashboard_agent", "rag_agent"]
    orchestrator_session_id = None

    for agent_type in built_in_types:
        existing = discovery.find_session_by_type(user_id, agent_type)
        if existing:
            if agent_type == "orchestrator":
                orchestrator_session_id = existing["session_id"]
            # Refresh heartbeat
            registry.heartbeat(existing["session_id"])
        else:
            session_id = str(uuid.uuid4())
            registry.register_session(
                user_id=user_id,
                session_id=session_id,
                agent_type=agent_type,
                capabilities={"built_in": True},
            )
            if agent_type == "orchestrator":
                orchestrator_session_id = session_id
            logger.info(
                "Auto-provisioned %s session %s for user %s",
                agent_type, session_id, user_id,
            )

    return orchestrator_session_id
