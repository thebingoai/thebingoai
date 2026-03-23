from sqlalchemy import Column, String, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class CustomAgent(Base, TimestampMixin):
    __tablename__ = "custom_agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=False)
    tool_keys = Column(JSON, nullable=False)           # List[str]
    connection_ids = Column(JSON, nullable=True)        # List[int] | None
    is_active = Column(Boolean, default=True, nullable=False)

    # Link to unified AgentProfile for cognitive configuration
    profile_id = Column(String, ForeignKey("agent_profiles.id"), nullable=True)

    # Agent mesh: autonomous execution
    is_autonomous = Column(Boolean, default=False, nullable=False)
    schedule = Column(String(100), nullable=True)  # cron expression, nullable

    # Relationships
    user = relationship("User")
    team = relationship("Team")
    profile = relationship("AgentProfile", foreign_keys=[profile_id])
