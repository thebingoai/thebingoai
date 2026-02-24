from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class Team(Base, TimestampMixin):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, ForeignKey("organizations.id"), nullable=False)
    name = Column(String, nullable=False)

    # Relationships
    organization = relationship("Organization")
    members = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_teams_org_name"),
    )
