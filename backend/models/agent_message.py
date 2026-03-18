from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index
from backend.database.base import Base
from datetime import datetime
import uuid


class AgentMessage(Base):
    """Inter-agent message for user-scoped communication."""

    __tablename__ = "agent_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    from_session_id = Column(
        String, ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    to_session_id = Column(
        String, ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False
    )
    message_type = Column(
        String(20), nullable=False, default="request"
    )  # request/response/notification/broadcast
    content = Column(JSON, nullable=False)
    correlation_id = Column(String, nullable=True, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/delivered/read/failed
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_agent_messages_to_status", "to_session_id", "status"),
        Index("ix_agent_messages_user_id", "user_id"),
    )
