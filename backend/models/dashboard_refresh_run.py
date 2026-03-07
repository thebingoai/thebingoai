"""DashboardRefreshRun — tracks each scheduled (or manual) dashboard refresh execution."""

from uuid import uuid4
from sqlalchemy import Column, String, Integer, Text, JSON, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from backend.database.base import Base


class DashboardRefreshRun(Base):
    __tablename__ = "dashboard_refresh_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    dashboard_id = Column(Integer, ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="running", nullable=False)  # running | completed | failed
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    widgets_total = Column(Integer, nullable=True)
    widgets_succeeded = Column(Integer, nullable=True)
    widgets_failed = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)           # top-level error message
    widget_errors = Column(JSON, nullable=True)   # {widget_id: "error msg", ...}

    dashboard = relationship("Dashboard", back_populates="refresh_runs")


Index("ix_dashboard_refresh_runs_dashboard_id", DashboardRefreshRun.dashboard_id)
