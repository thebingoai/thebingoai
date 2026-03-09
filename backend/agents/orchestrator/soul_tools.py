"""
soul_tools.py — Consolidated soul/personality management tool for the orchestrator.

Exposes 1 tool (consolidated from 2):
  update_personality — propose a soul update for review, or apply one after confirmation
"""

from langchain_core.tools import tool
from backend.agents.context import AgentContext
from typing import List, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)


def build_soul_tools(
    context: AgentContext,
    db_session_factory: Optional[Callable] = None,
) -> List:
    """
    Build the consolidated soul/personality management tool for the orchestrator.

    Returns an empty list when db_session_factory is not provided.

    Args:
        context: Agent execution context (carries user_id and related metadata).
        db_session_factory: Callable that returns a new SQLAlchemy DB session.

    Returns:
        [update_personality]
    """
    if db_session_factory is None:
        return []

    @tool
    async def update_personality(
        action: str,
        proposed_soul: str,
        reason: str = "",
    ) -> str:
        """
        Propose or apply a change to your soul — the persistent personality layer that
        shapes how you interact with this user across all conversations.

        **What the soul captures:**
        - Name: the identity you use in this context (e.g. "name: Aria")
        - Personality / tone: how you communicate (formal, casual, concise, detailed, etc.)
        - Domain context: the user's industry, role, or focus area you should be aware of
        - Communication preferences: formats the user prefers (markdown, bullet points, tables)

        Keep the soul under 500 words. Focus on *who you are*, not *what to do* —
        task instructions and domain workflows belong in skills or memories, not the soul.

        ---

        **action = "propose"**
        Stages a soul proposal for the user to review. Does NOT write to the database.
        Present the formatted proposal to the user and ask for explicit confirmation
        before calling update_personality again with action="apply".

        Required:
            proposed_soul: The full updated soul text (under 500 words).
            reason: A clear explanation of why you are proposing this change
                    (e.g. "You mentioned you prefer concise bullet-point answers").

        Returns a formatted proposal string ready to display to the user.

        ---

        **action = "apply"**
        Persists the approved soul text to the database. Only call this after the user
        has explicitly confirmed the proposal shown during action="propose".
        Never call apply without prior user confirmation.

        Required:
            proposed_soul: The soul text to save (should match what was proposed).

        Side effects:
          - Updates user.soul_prompt and increments user.soul_version.
          - If the soul contains a "name:" line, extracts the name and updates
            the permanent conversation title, then publishes a websocket event
            so connected clients receive the new title in real time.

        Returns JSON with success status and the new soul_version number.

        ---

        Args:
            action: "propose" to stage a proposal, "apply" to persist after confirmation.
            proposed_soul: The full soul text (both actions).
            reason: Why you are proposing this change (only used for action="propose").

        Returns:
            For "propose": JSON with a human-readable "proposal" string and the
                           raw "proposed_soul" text.
            For "apply":   JSON with "success", "message", and "soul_version".
        """
        if action == "propose":
            word_count = len(proposed_soul.split())
            if word_count > 600:
                return json.dumps({
                    "success": False,
                    "message": f"Soul is too long ({word_count} words). Keep it under 500 words.",
                })
            proposal = (
                f"I'd like to update my soul — the part of my personality that shapes how I work with you.\n\n"
                f"**Why:** {reason}\n\n"
                f"**Proposed soul:**\n---\n{proposed_soul}\n---\n\n"
                f"Would you like me to apply this?"
            )
            return json.dumps({"success": True, "proposal": proposal, "proposed_soul": proposed_soul})

        elif action == "apply":
            db = db_session_factory()
            try:
                from backend.models.user import User as UserModel
                from backend.models.conversation import Conversation
                user = db.query(UserModel).filter(UserModel.id == context.user_id).first()
                if not user:
                    return json.dumps({"success": False, "message": "User not found"})
                user.soul_prompt = proposed_soul
                user.soul_version = (user.soul_version or 0) + 1
                db.commit()
                # Extract name from soul text and update permanent conversation title
                for line in proposed_soul.splitlines():
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
                return json.dumps({
                    "success": True,
                    "message": "Soul updated successfully.",
                    "soul_version": user.soul_version,
                })
            except Exception as exc:
                db.rollback()
                logger.error(f"update_personality(apply) failed: {exc}")
                return json.dumps({"success": False, "message": str(exc)})
            finally:
                db.close()

        else:
            return json.dumps({
                "success": False,
                "message": f"Unknown action '{action}'. Must be 'propose' or 'apply'.",
            })

    return [update_personality]
