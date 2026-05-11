"""emit_briefing — terminal orchestrator tool that persists a structured briefing."""

import logging
from typing import Callable
from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agents.context import AgentContext
from backend.schemas.briefing import BriefingPayload

logger = logging.getLogger(__name__)


def _post_chat_message(db_session, *, user_id: str, briefing_id: int, headline: str) -> None:
    """Insert an assistant message into the user's permanent Bingo AI conversation."""
    from backend.models.message import Message
    from backend.services.conversation_service import ConversationService

    conv = ConversationService.get_or_create_permanent_conversation(db_session, user_id)

    msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=headline,
        source="heartbeat",
        briefing_id=briefing_id,
    )
    db_session.add(msg)


def _emit_ws(user_id: str, briefing_id: int) -> None:
    """Push briefing.ready event to the user via WebSocket (sync, Celery-safe)."""
    from backend.services.ws_connection_manager import ConnectionManager
    ConnectionManager.publish_to_user_sync(user_id, {
        "type": "briefing.ready",
        "briefing_id": briefing_id,
    })


def build_briefing_tools(
    context: AgentContext,
    db_session_factory: Callable,
    briefing_id: int,
) -> list:
    """Factory: returns [emit_briefing] bound to a specific briefing row."""

    @tool
    async def emit_briefing(payload: dict) -> str:
        """
        Deliver the final structured briefing for the current dashboard analysis.
        Call this exactly ONCE at the end of your analysis with the complete briefing payload.

        Args:
            payload: A BriefingPayload dict with keys:
                headline (str): one-line headline, ≤240 chars.
                deck (str): 1–2 sentence summary, ≤600 chars.
                kpis (list[Kpi]): 0–3 KPI tiles. Each: {label, value, delta_vs_prev?, delta_direction?}.
                sections (list[Section]): ≥1 numbered sections. Each: {heading, prose, widget_id?}.
                key_takeaways (list[str]): exactly 3 bullets.
        """
        try:
            validated = BriefingPayload.model_validate(payload)
        except ValidationError as e:
            logger.warning("emit_briefing validation failed for briefing %s: %s", briefing_id, e)
            return f"invalid briefing payload: {e.errors()[:3]}"

        db = db_session_factory()
        try:
            from backend.models.briefing import Briefing
            briefing = db.query(Briefing).filter(Briefing.id == briefing_id).first()
            if not briefing:
                return f"briefing {briefing_id} not found"
            if briefing.user_id != context.user_id:
                return "briefing user mismatch"

            briefing.payload = validated.model_dump()
            briefing.status = "ready"
            briefing.error = None

            _post_chat_message(db, user_id=context.user_id, briefing_id=briefing_id, headline=validated.headline)
            db.commit()

            _emit_ws(context.user_id, briefing_id)
            return f"briefing {briefing_id} ready"
        except Exception as e:
            db.rollback()
            logger.exception("emit_briefing persistence failed: %s", e)
            return f"persistence error: {e}"
        finally:
            db.close()

    return [emit_briefing]
