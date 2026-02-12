from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)  # LangGraph thread ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)  # Auto-generated from first message

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
