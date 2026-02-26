from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class SkillReference(Base, TimestampMixin):
    __tablename__ = "skill_references"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    skill_id = Column(String, ForeignKey("user_skills.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    skill = relationship("UserSkill", back_populates="references")

    __table_args__ = (
        Index("ix_skill_references_skill_id", "skill_id"),
    )
