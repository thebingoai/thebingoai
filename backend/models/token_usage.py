from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime
import enum


class OperationType(str, enum.Enum):
    CHAT = "chat"
    MEMORY_GENERATION = "memory_generation"
    QUERY_GENERATION = "query_generation"
    EMBEDDING = "embedding"


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    operation = Column(Enum(OperationType), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)  # In USD
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="token_usage")
