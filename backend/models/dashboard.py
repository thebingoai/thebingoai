from sqlalchemy import Column, Integer, String, Text, JSON, ForeignKey, Boolean, DateTime, Index
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin


class Dashboard(Base, TimestampMixin):
    __tablename__ = "dashboards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    widgets = Column(JSON, nullable=False, default=list)

    # Schedule columns
    schedule_type = Column(String(10), nullable=True)       # "preset" | "cron" | NULL (no schedule)
    schedule_value = Column(String(100), nullable=True)     # e.g. "1h", "*/15 * * * *"
    cron_expression = Column(String(100), nullable=True)    # normalized cron string
    schedule_active = Column(Boolean, default=False, nullable=False)
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="dashboards")
    refresh_runs = relationship("DashboardRefreshRun", back_populates="dashboard", cascade="all, delete-orphan")


# Composite index for dispatcher queries
Index("ix_dashboards_schedule_active_next_run", Dashboard.schedule_active, Dashboard.next_run_at)
