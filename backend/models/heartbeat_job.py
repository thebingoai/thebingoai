from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index
from backend.database.base import Base, TimestampMixin
import uuid


class HeartbeatJob(Base, TimestampMixin):
    __tablename__ = "heartbeat_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    prompt = Column(Text, nullable=False)
    schedule_type = Column(String(10), nullable=False)  # "preset" or "cron"
    schedule_value = Column(String(100), nullable=False)  # e.g. "30m", "0 */2 * * *"
    cron_expression = Column(String(100), nullable=False)  # normalized cron string
    agent_type = Column(String(50), nullable=True)  # None = orchestrator (default), "monitor_agent", etc.
    is_active = Column(Boolean, default=True, nullable=False)
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_heartbeat_jobs_user_id", "user_id"),
        Index("ix_heartbeat_jobs_active_next_run", "is_active", "next_run_at"),
    )
