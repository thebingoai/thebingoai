from sqlalchemy import Column, String, ForeignKey, JSON, Text, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin
import uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    sso_id = Column(String, unique=True, nullable=True, index=True)
    auth_provider = Column(String, nullable=False, default="sso")
    org_id = Column(String, ForeignKey("organizations.id"), nullable=True)
    preferences = Column(JSON, nullable=True)  # {"name": "Ed", "role": "PM", "tone": "concise"}
    soul_prompt = Column(Text, nullable=True)
    soul_version = Column(Integer, nullable=False, default=0)

    # Terms & Conditions (enterprise)
    accepted_tos = Column(Boolean, nullable=True, default=False)
    tos_accepted_at = Column(DateTime, nullable=True)
    tos_version = Column(String(20), nullable=True)

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
    dashboards = relationship(
        "Dashboard", back_populates="user", cascade="all, delete-orphan"
    )
    agent_sessions = relationship(
        "AgentSession", back_populates="user", cascade="all, delete-orphan"
    )
