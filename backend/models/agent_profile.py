"""
AgentProfile — unified cognitive configuration for all agent types.

Every agent in the system (orchestrator, data_agent, dashboard_agent, monitor_agent,
and user-created custom agents) uses AgentProfile as its source of truth for prompt
building. The 8 sections map to the OpenClaw-inspired cognitive architecture:

    identity, soul, tools, agents, bootstrap, heartbeat, user_context, guardrails

Profiles support org → team → user inheritance for enterprise.
"""

from sqlalchemy import Column, String, Boolean, Integer, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class AgentProfile(Base, TimestampMixin):
    __tablename__ = "agent_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Hierarchy: org → team → user. Nullable fields determine the level.
    # org only (team=null, user=null) → org baseline
    # org + team (user=null) → team defaults
    # org + team + user → user customization
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)

    agent_type = Column(String(50), nullable=False)  # "orchestrator", "data_agent", etc.

    # --- 8 cognitive architecture sections ---
    identity = Column(Text, nullable=False)        # Who am I, what can I do
    soul = Column(Text, nullable=True)             # Personality, tone, values
    tools = Column(Text, nullable=True)            # How I use my tools, guidelines
    agents = Column(Text, nullable=True)           # Sub-agents I can delegate to
    bootstrap = Column(Text, nullable=True)        # First-run behavior
    heartbeat = Column(Text, nullable=True)        # Recurring checks, context refresh rules
    user_context = Column(Text, nullable=True)     # User-specific preferences and notes
    guardrails = Column(Text, nullable=True)       # Constraints, boundaries, forbidden behaviors

    # Section-level locking for enterprise governance
    # {"identity": "locked", "soul": "open", "guardrails": "locked", ...}
    # Levels: "locked" (immutable), "seeded" (customizable), "open" (free)
    section_locks = Column(JSON, default=dict)

    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[org_id])
    team = relationship("Team", foreign_keys=[team_id])
