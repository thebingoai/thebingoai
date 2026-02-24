from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, DateTime, UniqueConstraint
from backend.database.base import Base
from datetime import datetime
import uuid


class TeamConnectionPolicy(Base):
    __tablename__ = "team_connection_policies"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("team_id", "connection_id", name="uq_team_connection_policies_team_conn"),
    )
