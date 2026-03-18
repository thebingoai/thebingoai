from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
from datetime import datetime
import uuid


class AgentSession(Base, TimestampMixin):
    """Persistent user-owned agent identity for the peer-to-peer mesh."""

    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_type = Column(String(50), nullable=False)  # e.g. "data_agent", "dashboard_agent"
    agent_definition_id = Column(
        String, ForeignKey("custom_agents.id", ondelete="SET NULL"), nullable=True
    )
    status = Column(String(20), nullable=False, default="active")  # active/idle/terminated
    capabilities = Column(JSON, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="agent_sessions")
    agent_definition = relationship("CustomAgent")

    __table_args__ = (
        Index("ix_agent_sessions_user_id", "user_id"),
        Index("ix_agent_sessions_user_type", "user_id", "agent_type"),
    )
