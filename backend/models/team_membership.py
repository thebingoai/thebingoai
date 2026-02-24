from sqlalchemy import Column, String, ForeignKey, Enum, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime
import enum
import uuid


class MemberRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=False)
    role = Column(
        Enum(MemberRole, values_callable=lambda objs: [e.value for e in objs], create_type=False),
        nullable=False,
        default=MemberRole.MEMBER,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("User")
    team = relationship("Team", back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_team_memberships_user_team"),
    )
