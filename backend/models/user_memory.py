from sqlalchemy import Column, String, Text, Boolean, ForeignKey, Index
from backend.database.base import Base, TimestampMixin
import uuid


class UserMemory(Base, TimestampMixin):
    __tablename__ = "user_memories"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_user_memories_user_id", "user_id"),
    )
