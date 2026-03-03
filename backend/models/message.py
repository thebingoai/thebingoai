from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String(20), nullable=False, default="chat", server_default="chat")  # "chat" | "heartbeat" | "system" | "context_reset"
    heartbeat_job_id = Column(String, ForeignKey("heartbeat_jobs.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    agent_steps = relationship("AgentStep", back_populates="message", cascade="all, delete-orphan")
