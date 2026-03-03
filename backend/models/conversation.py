from sqlalchemy import Column, String, Integer, ForeignKey, Index, text
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    thread_id = Column(String, unique=True, nullable=False, index=True)  # LangGraph thread ID
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=True)  # Auto-generated from first message
    type = Column(String(20), nullable=False, default="task", server_default="task")

    __table_args__ = (
        Index(
            "ix_conversations_user_permanent",
            "user_id",
            unique=True,
            postgresql_where=text("type = 'permanent'"),
        ),
    )

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.timestamp")
