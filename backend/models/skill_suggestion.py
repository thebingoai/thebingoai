from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base, TimestampMixin
import uuid


class SkillSuggestion(Base, TimestampMixin):
    __tablename__ = "skill_suggestions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    suggested_name = Column(String, nullable=False)
    suggested_description = Column(Text, nullable=True)
    suggested_skill_type = Column(String(20), nullable=False, default="instruction")
    suggested_instructions = Column(Text, nullable=True)
    pattern_summary = Column(Text, nullable=True)
    source_conversation_ids = Column(JSONB, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="pending")
    recommendation = Column(String(20), nullable=True)
    recommendation_reason = Column(Text, nullable=True)
    frequency_count = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_skill_suggestions_user_status", "user_id", "status"),
    )
