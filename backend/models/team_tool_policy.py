from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, UniqueConstraint
from backend.database.base import Base
from datetime import datetime
import uuid


class TeamToolPolicy(Base):
    __tablename__ = "team_tool_policies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    tool_key = Column(String, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("team_id", "tool_key", name="uq_team_tool_policies_team_tool"),
    )
