"""Persist Layer-4 unresolved turns for later review.

Called from chat handlers when the orchestrator retry still fails the judge.
Writes one row to `agent_failure_case`. Paired with CreditContextManager.void()
so the user isn't charged for an unresolved turn.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.models.agent_failure_case import AgentFailureCase

logger = logging.getLogger(__name__)


def capture_failure(
    db: Session,
    user_id: str,
    conversation_id: Optional[int],
    thread_id: Optional[str],
    user_question: str,
    response_initial: str,
    response_after_retry: str,
    judge_reason_initial: str,
    judge_reason_retry: str,
    judge_directive: str,
    model: Optional[str],
    judge_model: Optional[str],
    orchestrator_steps: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Insert a single agent_failure_case row.

    Swallows exceptions so a capture failure never breaks the user's chat reply.
    """
    try:
        row = AgentFailureCase(
            user_id=user_id,
            conversation_id=conversation_id,
            thread_id=thread_id,
            user_question=user_question or "",
            response_initial=response_initial or "",
            response_after_retry=response_after_retry or "",
            judge_reason_initial=judge_reason_initial or "",
            judge_reason_retry=judge_reason_retry or "",
            judge_directive=judge_directive or "",
            orchestrator_steps=orchestrator_steps,
            model=model,
            judge_model=judge_model,
        )
        db.add(row)
        db.commit()
        logger.info(
            "[layer4] captured failure case user=%s thread=%s reason=%s",
            user_id, thread_id, judge_reason_retry,
        )
    except Exception as exc:
        logger.warning("[layer4] failed to capture failure case: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
