from sqlalchemy import Column, String, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_skill_name"),
    )
