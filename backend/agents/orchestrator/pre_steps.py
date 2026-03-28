"""
pre_steps.py — Deterministic pre-response actions for the orchestrator.

Pre-steps run before the LLM ReAct loop on every orchestrator invocation.
They handle housekeeping that shouldn't depend on LLM judgment:
profile sync, bootstrap gating, context preloading, etc.

To add a new pre-step:
  1. Define an async function matching PreStep signature
  2. Register it in ORCHESTRATOR_PRE_STEPS
"""

from dataclasses import dataclass
from typing import Callable, Awaitable, List, Optional
import logging

logger = logging.getLogger(__name__)

# Type alias for pre-step functions
PreStep = Callable[["PreStepContext"], Awaitable[None]]


@dataclass
class PreStepContext:
    user_id: str
    query: str
    profile: object  # AgentProfile
    user_memories_context: str
    db_session_factory: Optional[Callable] = None


# ---------------------------------------------------------------------------
# Pre-step: bootstrap_check
# ---------------------------------------------------------------------------

async def bootstrap_check(ctx: PreStepContext) -> None:
    """Skip bootstrap if user has prior interaction history."""
    if ctx.user_memories_context:
        ctx.profile._skip_bootstrap = True
        logger.debug("bootstrap_check: skipping bootstrap (user_memories exist)")


# ---------------------------------------------------------------------------
# Pre-step: profile_sync
# ---------------------------------------------------------------------------

async def profile_sync(ctx: PreStepContext) -> None:
    """Auto-populate user_context from user_memories if still default."""
    if not ctx.user_memories_context or not ctx.db_session_factory:
        return

    # Check if user_context is still the default template (empty Name field)
    uc = ctx.profile.user_context or ""
    if uc and "- **Name:**\n" not in uc:
        return  # already customized by the agent

    # Build user_context from the formatted memories string
    new_context = (
        "## About This User\n\n"
        "_(Auto-synced from conversation memories.)_\n\n"
        f"{ctx.user_memories_context}\n"
    )

    ctx.profile.user_context = new_context

    # Persist to DB
    db = ctx.db_session_factory()
    try:
        from backend.models.agent_profile import AgentProfile
        profile = db.query(AgentProfile).filter(
            AgentProfile.id == ctx.profile.id,
        ).first()
        if profile:
            profile.user_context = new_context
            profile.version = (profile.version or 0) + 1
            db.commit()
            logger.info("profile_sync: updated user_context from user_memories")
    except Exception as exc:
        db.rollback()
        logger.warning("profile_sync: failed to update user_context: %s", exc)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Registry — order matters: earlier steps run first
# ---------------------------------------------------------------------------

ORCHESTRATOR_PRE_STEPS: List[PreStep] = [
    bootstrap_check,
    profile_sync,
]


async def run_pre_steps(ctx: PreStepContext) -> None:
    """Execute all registered pre-steps in order."""
    for step in ORCHESTRATOR_PRE_STEPS:
        try:
            await step(ctx)
        except Exception as exc:
            logger.warning("Pre-step %s failed: %s", step.__name__, exc)
