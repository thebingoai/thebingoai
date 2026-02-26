from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index
from backend.database.base import Base
import uuid


class HeartbeatJobRun(Base):
    __tablename__ = "heartbeat_job_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("heartbeat_jobs.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default="running")  # running/completed/failed
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    prompt = Column(Text, nullable=True)  # snapshot of prompt at run time
    response = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_heartbeat_job_runs_job_id", "job_id"),
    )
