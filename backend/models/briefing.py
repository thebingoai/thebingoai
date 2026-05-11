from sqlalchemy import Column, BigInteger, Integer, String, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base


class Briefing(Base):
    __tablename__ = "briefings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    dashboard_id = Column(Integer, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(20), nullable=False)
    heartbeat_job_id = Column(String, ForeignKey("heartbeat_jobs.id", ondelete="SET NULL"), nullable=True)
    date_range_from = Column(DateTime(timezone=True), nullable=True)
    date_range_to = Column(DateTime(timezone=True), nullable=True)
    payload = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, server_default="generating")
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
