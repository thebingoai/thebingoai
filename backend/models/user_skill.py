from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class UserSkill(Base, TimestampMixin):
    __tablename__ = "user_skills"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    prompt_template = Column(Text, nullable=True)
    code = Column(Text, nullable=True)
    parameters_schema = Column(JSONB, nullable=True)
    secrets = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    skill_type = Column(String(20), nullable=False, default="code")
    instructions = Column(Text, nullable=True)
    activation_hint = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)

    references = relationship("SkillReference", back_populates="skill", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_skill_name"),
    )
