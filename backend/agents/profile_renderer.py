"""
profile_renderer.py — Resolves and renders AgentProfile into final prompt strings.

Two main operations:
  resolve() — merge org → team → user profiles (user wins if set)
  render()  — assemble final prompt from profile sections + runtime context
"""

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy.orm import Session

from backend.agents.profile_defaults import DEFAULTS, SECTIONS, get_default_section

if TYPE_CHECKING:
    from backend.models.agent_profile import AgentProfile
    from backend.models.custom_agent import CustomAgent
    from backend.models.user_skill import UserSkill

import logging

logger = logging.getLogger(__name__)


@dataclass
class RuntimeContext:
    """Dynamic context injected alongside the static profile at render time."""
    custom_agents: list = field(default_factory=list)
    user_skills: list = field(default_factory=list)
    skill_suggestions: list = field(default_factory=list)
    user_memories_context: str = ""
    memory_context: str = ""
    available_connections: Optional[List[int]] = None
    connection_metadata: list = field(default_factory=list)
    mesh_enabled: bool = False
    target_connection_id: Optional[int] = None


class ProfileRenderer:
    """Resolves profile hierarchy and renders final prompts."""

    @staticmethod
    def resolve(
        db: Session,
        agent_type: str,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> "AgentProfile":
        """
        Resolve the effective profile by merging org → team → user.

        For each section: user value wins if set, else team, else org, else default.
        Returns a transient AgentProfile (not committed) with merged content.
        """
        from backend.models.agent_profile import AgentProfile

        profiles = []

        # Load profiles from most general to most specific
        if org_id:
            org_profile = db.query(AgentProfile).filter(
                AgentProfile.org_id == org_id,
                AgentProfile.team_id.is_(None),
                AgentProfile.user_id.is_(None),
                AgentProfile.agent_type == agent_type,
                AgentProfile.is_active.is_(True),
            ).first()
            if org_profile:
                profiles.append(org_profile)

        if team_id:
            team_profile = db.query(AgentProfile).filter(
                AgentProfile.team_id == team_id,
                AgentProfile.user_id.is_(None),
                AgentProfile.agent_type == agent_type,
                AgentProfile.is_active.is_(True),
            ).first()
            if team_profile:
                profiles.append(team_profile)

        if user_id:
            user_profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == user_id,
                AgentProfile.agent_type == agent_type,
                AgentProfile.is_active.is_(True),
            ).first()
            if user_profile:
                profiles.append(user_profile)

        if not profiles:
            # No profiles at any level — create a transient default
            return ProfileRenderer._build_default_profile(agent_type, user_id, team_id, org_id)

        # Merge: later profiles (more specific) override earlier ones per-section
        # Also collect section_locks from all levels (most restrictive wins)
        merged_locks = {}
        merged_values = {}

        for section in SECTIONS:
            default_val = get_default_section(agent_type, section)
            merged_values[section] = default_val  # start with default

        for profile in profiles:
            for section in SECTIONS:
                value = getattr(profile, section, None)
                if value is not None:
                    merged_values[section] = value
            # Merge locks — "locked" > "seeded" > "open"
            profile_locks = profile.section_locks or {}
            for section, lock_level in profile_locks.items():
                existing = merged_locks.get(section, "open")
                if _lock_priority(lock_level) > _lock_priority(existing):
                    merged_locks[section] = lock_level

        # Build a transient AgentProfile with merged values
        resolved = AgentProfile(
            agent_type=agent_type,
            user_id=user_id,
            team_id=team_id,
            org_id=org_id,
            identity=merged_values.get("identity", ""),
            soul=merged_values.get("soul"),
            tools=merged_values.get("tools"),
            agents=merged_values.get("agents"),
            bootstrap=merged_values.get("bootstrap"),
            heartbeat=merged_values.get("heartbeat"),
            user_context=merged_values.get("user_context"),
            guardrails=merged_values.get("guardrails"),
            section_locks=merged_locks,
            is_active=True,
            version=profiles[-1].version if profiles else 1,
        )
        # Carry the DB id from the most specific profile for updates
        resolved.id = profiles[-1].id
        return resolved

    @staticmethod
    def render(
        profile: "AgentProfile",
        runtime_context: Optional[RuntimeContext] = None,
    ) -> str:
        """
        Assemble the final prompt string from profile sections + runtime context.

        Section order:
          1. identity (always)
          2. soul or bootstrap (mutually exclusive)
          3. guardrails (always, if set)
          4. agents (static + dynamic custom_agents)
          5. runtime injections (skills, memories, connections)
          6. tools (static guidelines)
          7. heartbeat (static rules)
        """
        ctx = runtime_context or RuntimeContext()
        sections: List[str] = []

        # 1. Identity (always present)
        if profile.identity:
            sections.append(profile.identity)

        # 2. Soul or Bootstrap (mutually exclusive)
        if profile.soul:
            sections.append(f"## Your Personality & Approach\n{profile.soul}")
        elif profile.bootstrap:
            sections.append(f"## Identity Setup\n{profile.bootstrap}")

        # 3. Guardrails (always, if set)
        if profile.guardrails:
            sections.append(profile.guardrails)

        # 4. Agents section (static from profile + dynamic from runtime)
        if profile.agents:
            sections.append(profile.agents)
        if ctx.custom_agents:
            sections.append(_format_agent_list(ctx.custom_agents))

        # 5. Runtime context injections
        if ctx.user_skills:
            sections.append(_format_skills(ctx.user_skills))

        if ctx.skill_suggestions:
            sections.append(_format_suggestions(ctx.skill_suggestions))

        if ctx.user_memories_context:
            sections.append(f"## User Preferences & Instructions\n{ctx.user_memories_context}")

        if ctx.memory_context:
            sections.append(f"## Relevant Past Context\n{ctx.memory_context}")

        if ctx.available_connections:
            if ctx.connection_metadata:
                lines = [
                    f'- ID {c.id}: "{c.name}" ({c.db_type}, database: {c.database})'
                    for c in ctx.connection_metadata
                ]
                connections_str = "\n".join(lines)
            else:
                connections_str = ", ".join(str(c) for c in ctx.available_connections)
            section = f"## Available Database Connections\n{connections_str}"
            section += "\nUse these for dataSource.connectionId in dashboard widgets."
            if ctx.target_connection_id is not None:
                section += (
                    f"\n\nPrimary connection to use: {ctx.target_connection_id}"
                    "\nFocus your schema exploration on this connection. "
                    "Only explore other connections if the user explicitly asks."
                )
            sections.append(section)

        # 6. Tools (static guidelines from profile)
        if profile.tools:
            sections.append(profile.tools)

        # 7. Heartbeat (static rules from profile)
        if profile.heartbeat:
            sections.append(profile.heartbeat)

        return "\n\n".join(sections)

    @staticmethod
    def _build_default_profile(
        agent_type: str,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> "AgentProfile":
        """Create a transient AgentProfile from hardcoded defaults."""
        from backend.models.agent_profile import AgentProfile

        defaults = DEFAULTS.get(agent_type, {})
        return AgentProfile(
            agent_type=agent_type,
            user_id=user_id,
            team_id=team_id,
            org_id=org_id,
            identity=defaults.get("identity", f"You are a {agent_type} agent."),
            soul=defaults.get("soul"),
            tools=defaults.get("tools"),
            agents=defaults.get("agents"),
            bootstrap=defaults.get("bootstrap"),
            heartbeat=defaults.get("heartbeat"),
            user_context=defaults.get("user_context"),
            guardrails=defaults.get("guardrails"),
            section_locks={},
            is_active=True,
            version=0,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCK_PRIORITY = {"open": 0, "seeded": 1, "locked": 2}


def _lock_priority(level: str) -> int:
    return _LOCK_PRIORITY.get(level, 0)


def _format_agent_list(custom_agents: list) -> str:
    """Format a list of CustomAgent objects into a prompt section."""
    descriptions = []
    for i, agent in enumerate(custom_agents, 1):
        desc = getattr(agent, "description", None) or "No description provided."
        name = getattr(agent, "name", f"Agent {i}")
        descriptions.append(f"{i}. **{name}**: {desc}")
    return f"## Available Agents ({len(custom_agents)})\n" + "\n".join(descriptions)


def _format_skills(user_skills: list) -> str:
    """Format a list of UserSkill objects into a prompt section."""
    skill_lines = "\n".join(
        f"- **{s.name}** [{getattr(s, 'skill_type', 'code') or 'code'}]: {s.description}"
        for s in user_skills
    )
    return (
        f"## Available Custom Skills ({len(user_skills)})\n"
        f"Call `get_skill` to load a skill's full content before using it:\n{skill_lines}"
    )


def _format_suggestions(skill_suggestions: list) -> str:
    """Format skill suggestions into a prompt section."""
    suggestion_lines = "\n".join(
        f"- **{s.get('suggested_name')}** (confidence: {s.get('confidence', 0):.2f}): "
        f"{s.get('pattern_summary', '')}"
        for s in skill_suggestions
    )
    return (
        "## Pending Skill Suggestions\n"
        "Background analysis detected these patterns. Mention them naturally when relevant:\n"
        + suggestion_lines
    )


def seed_default_profile(
    db: Session,
    user_id: str,
    agent_type: str,
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    soul_prompt: Optional[str] = None,
) -> "AgentProfile":
    """
    Create and persist a default AgentProfile for a user.

    Used for lazy-seeding on first chat or during data migration.
    """
    from backend.models.agent_profile import AgentProfile

    defaults = DEFAULTS.get(agent_type, {})
    profile = AgentProfile(
        user_id=user_id,
        org_id=org_id,
        team_id=team_id,
        agent_type=agent_type,
        identity=defaults.get("identity", f"You are a {agent_type} agent."),
        soul=soul_prompt or defaults.get("soul"),
        tools=defaults.get("tools"),
        agents=defaults.get("agents"),
        bootstrap=defaults.get("bootstrap"),
        heartbeat=defaults.get("heartbeat"),
        user_context=defaults.get("user_context"),
        guardrails=defaults.get("guardrails"),
        section_locks={},
        is_active=True,
        version=1,
    )
    db.add(profile)
    db.flush()
    return profile
