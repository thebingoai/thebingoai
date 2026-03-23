"""
profile_tools.py — Self-evolution tools for the agent's cognitive profile.

Extends the existing update_personality pattern (soul_tools.py) to all 8 profile
sections. The agent can propose and apply changes to its own identity, soul, tools,
agents, bootstrap, heartbeat, and user_context. Guardrails are read-only.
"""

from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.agents.profile_defaults import SECTIONS
from typing import List, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)

# Sections the agent can self-modify
_EVOLVABLE_SECTIONS = [s for s in SECTIONS if s != "guardrails"]

# High-impact sections that always require user confirmation before apply
_HIGH_IMPACT_SECTIONS = {"identity", "tools", "agents", "bootstrap", "heartbeat"}

# Low-friction sections — agent can propose + apply with less ceremony
_LOW_FRICTION_SECTIONS = {"soul", "user_context"}


def build_profile_tools(
    context: AgentContext,
    db_session_factory: Optional[Callable] = None,
) -> List:
    """
    Build profile self-evolution tools for the orchestrator.

    Returns [update_profile, read_profile].
    """
    if db_session_factory is None:
        return []

    @tool
    async def update_profile(
        section: str,
        action: str,
        proposed_content: str,
        reason: str = "",
    ) -> str:
        """
        Propose or apply a change to a section of your agent profile.

        Your profile defines your cognitive architecture — who you are, how you
        behave, and what you can do. Each section can evolve based on interactions.

        **Sections you can update:**
        - identity: Your role, expertise, and boundaries
        - soul: Your personality, tone, and values (under 500 words)
        - tools: How you use your available tools
        - agents: Sub-agents you can delegate to
        - bootstrap: Your first-run behavior with new users
        - heartbeat: What you check periodically
        - user_context: Notes about this specific user's preferences

        **Sections you CANNOT update:**
        - guardrails: Read-only constraints set by admins

        **action = "propose"**
        Stages a proposal for the user to review. Does NOT write to the database.
        Present the proposal and ask for explicit confirmation before applying.

        **action = "apply"**
        Persists the change after user confirmation. Never call without prior approval.

        Args:
            section: Which profile section to update.
            action: "propose" to stage, "apply" to persist.
            proposed_content: The full updated section content.
            reason: Why you are proposing this change.

        Returns:
            JSON with success status and proposal/result details.
        """
        # Validate section
        if section not in _EVOLVABLE_SECTIONS:
            if section == "guardrails":
                return json.dumps({
                    "success": False,
                    "message": "Cannot modify guardrails — this section is read-only and managed by admins.",
                })
            return json.dumps({
                "success": False,
                "message": f"Unknown section '{section}'. Valid: {', '.join(_EVOLVABLE_SECTIONS)}",
            })

        if action == "propose":
            # Word count check for soul
            if section == "soul":
                word_count = len(proposed_content.split())
                if word_count > 600:
                    return json.dumps({
                        "success": False,
                        "message": f"Soul is too long ({word_count} words). Keep it under 500 words.",
                    })

            # Check section locks
            lock_status = _check_section_lock(db_session_factory, context.user_id, section)
            if lock_status == "locked":
                return json.dumps({
                    "success": False,
                    "message": f"Cannot update '{section}' — locked by your organization admin.",
                })

            impact = "high-impact" if section in _HIGH_IMPACT_SECTIONS else "low-friction"
            proposal = (
                f"I'd like to update my **{section}** profile section.\n\n"
                f"**Why:** {reason}\n\n"
                f"**Proposed {section}:**\n---\n{proposed_content}\n---\n\n"
            )
            if impact == "high-impact":
                proposal += "This is a high-impact change. Would you like me to apply this?"
            else:
                proposal += "Would you like me to apply this?"

            return json.dumps({
                "success": True,
                "proposal": proposal,
                "section": section,
                "proposed_content": proposed_content,
            })

        elif action == "apply":
            db = db_session_factory()
            try:
                from backend.models.agent_profile import AgentProfile

                profile = db.query(AgentProfile).filter(
                    AgentProfile.user_id == context.user_id,
                    AgentProfile.agent_type == "orchestrator",
                    AgentProfile.is_active.is_(True),
                ).first()

                if not profile:
                    # Lazy-seed if no profile exists
                    from backend.agents.profile_renderer import seed_default_profile
                    from backend.models.user import User as UserModel
                    user = db.query(UserModel).filter(UserModel.id == context.user_id).first()
                    profile = seed_default_profile(
                        db, context.user_id, "orchestrator",
                        org_id=getattr(user, "org_id", None),
                    )

                # Check lock
                locks = profile.section_locks or {}
                if locks.get(section) == "locked":
                    return json.dumps({
                        "success": False,
                        "message": f"Cannot update '{section}' — locked by your organization admin.",
                    })

                # Apply the change
                setattr(profile, section, proposed_content)
                profile.version = (profile.version or 0) + 1
                db.commit()

                # Special handling for soul: extract name and update conversation title
                if section == "soul":
                    _handle_soul_side_effects(db, context, proposed_content)

                return json.dumps({
                    "success": True,
                    "message": f"Profile section '{section}' updated successfully.",
                    "version": profile.version,
                })
            except Exception as exc:
                db.rollback()
                logger.error(f"update_profile(apply, {section}) failed: {exc}")
                return json.dumps({"success": False, "message": str(exc)})
            finally:
                db.close()

        else:
            return json.dumps({
                "success": False,
                "message": f"Unknown action '{action}'. Must be 'propose' or 'apply'.",
            })

    @tool
    async def read_profile(section: str = "") -> str:
        """
        Read your current agent profile or a specific section.

        Use this to introspect on your own configuration — understand who you are,
        what tools you have, what your guardrails say, etc.

        Args:
            section: Specific section to read (e.g. "identity", "guardrails").
                     Leave empty to see all sections.

        Returns:
            JSON with the requested profile content.
        """
        db = db_session_factory()
        try:
            from backend.models.agent_profile import AgentProfile

            profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == context.user_id,
                AgentProfile.agent_type == "orchestrator",
                AgentProfile.is_active.is_(True),
            ).first()

            if not profile:
                return json.dumps({
                    "success": True,
                    "message": "No profile found — using defaults.",
                    "profile": {},
                })

            if section:
                if section not in SECTIONS:
                    return json.dumps({
                        "success": False,
                        "message": f"Unknown section '{section}'. Valid: {', '.join(SECTIONS)}",
                    })
                content = getattr(profile, section, None)
                lock = (profile.section_locks or {}).get(section, "open")
                return json.dumps({
                    "success": True,
                    "section": section,
                    "content": content or "(empty)",
                    "lock_level": lock,
                    "version": profile.version,
                })

            # Return all sections
            all_sections = {}
            locks = profile.section_locks or {}
            for s in SECTIONS:
                content = getattr(profile, s, None)
                all_sections[s] = {
                    "content": content[:200] + "..." if content and len(content) > 200 else content,
                    "lock_level": locks.get(s, "open"),
                }
            return json.dumps({
                "success": True,
                "agent_type": profile.agent_type,
                "version": profile.version,
                "sections": all_sections,
            })
        except Exception as exc:
            logger.error(f"read_profile failed: {exc}")
            return json.dumps({"success": False, "message": str(exc)})
        finally:
            db.close()

    return [update_profile, read_profile]


def _check_section_lock(
    db_session_factory: Callable,
    user_id: str,
    section: str,
) -> str:
    """Check the effective lock level for a section across the profile hierarchy."""
    db = db_session_factory()
    try:
        from backend.models.agent_profile import AgentProfile
        from backend.models.user import User as UserModel

        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return "open"

        # Check org-level and team-level locks
        org_id = getattr(user, "org_id", None)

        lock_priority = {"open": 0, "seeded": 1, "locked": 2}
        effective_lock = "open"

        # Check org profile locks
        if org_id:
            org_profile = db.query(AgentProfile).filter(
                AgentProfile.org_id == org_id,
                AgentProfile.team_id.is_(None),
                AgentProfile.user_id.is_(None),
                AgentProfile.agent_type == "orchestrator",
                AgentProfile.is_active.is_(True),
            ).first()
            if org_profile and org_profile.section_locks:
                org_lock = org_profile.section_locks.get(section, "open")
                if lock_priority.get(org_lock, 0) > lock_priority.get(effective_lock, 0):
                    effective_lock = org_lock

        return effective_lock
    except Exception:
        return "open"
    finally:
        db.close()


def _handle_soul_side_effects(db, context: AgentContext, soul_text: str):
    """Handle soul-specific side effects: extract name, update conversation title."""
    try:
        from backend.models.conversation import Conversation

        for line in soul_text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("name:"):
                extracted_name = stripped.split(":", 1)[1].strip()
                if extracted_name:
                    perm_conv = db.query(Conversation).filter(
                        Conversation.user_id == context.user_id,
                        Conversation.type == "permanent",
                    ).first()
                    if perm_conv:
                        perm_conv.title = extracted_name
                        db.commit()
                        from backend.services.ws_connection_manager import ConnectionManager
                        ConnectionManager.publish_to_user_sync(context.user_id, {
                            "type": "chat.title",
                            "thread_id": perm_conv.thread_id,
                            "content": extracted_name,
                        })
                break
    except Exception as exc:
        logger.warning(f"Soul side-effects failed: {exc}")
