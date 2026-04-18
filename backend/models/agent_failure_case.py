from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from backend.database.base import Base


class AgentFailureCase(Base):
    """Captured failure when Layer-4 retry still fails the response-quality judge.

    One row per turn where the orchestrator produced an unresolved response
    and the single retry also failed the judge. The turn's credit is voided
    (see CreditContextManager.void) and this row is written for later review.
    """

    __tablename__ = "agent_failure_case"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, index=True)
    thread_id = Column(String, nullable=True, index=True)

    user_question = Column(Text, nullable=False)
    response_initial = Column(Text, nullable=False, server_default="")
    response_after_retry = Column(Text, nullable=False, server_default="")

    judge_reason_initial = Column(Text, nullable=False, server_default="")
    judge_reason_retry = Column(Text, nullable=False, server_default="")
    judge_directive = Column(Text, nullable=False, server_default="")

    orchestrator_steps = Column(JSONB, nullable=True)

    model = Column(String, nullable=True)
    judge_model = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
