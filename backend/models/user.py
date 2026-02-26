from sqlalchemy import Column, String, ForeignKey, JSON, Text, Integer
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    preferences = Column(JSON, nullable=True)
    soul_prompt = Column(Text, nullable=True)
    soul_version = Column(Integer, nullable=False, default=0)

    # Relationships
    database_connections = relationship(
        "DatabaseConnection", back_populates="user", cascade="all, delete-orphan"
    )
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    token_usage = relationship(
        "TokenUsage", back_populates="user", cascade="all, delete-orphan"
    )
