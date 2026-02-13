from sqlalchemy.orm import Session
from backend.models.conversation import Conversation
from backend.models.message import Message
from typing import Optional, List
import uuid


class ConversationService:
    """Service for managing conversations and messages."""

    @staticmethod
    def create_conversation(db: Session, user_id: str, title: Optional[str] = None) -> Conversation:
        """Create a new conversation."""
        thread_id = str(uuid.uuid4())

        conversation = Conversation(
            thread_id=thread_id,
            user_id=user_id,
            title=title or "New Chat"
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation

    @staticmethod
    def get_conversation_by_thread(db: Session, thread_id: str, user_id: str) -> Optional[Conversation]:
        """Get conversation by thread ID."""
        return db.query(Conversation).filter(
            Conversation.thread_id == thread_id,
            Conversation.user_id == user_id
        ).first()

    @staticmethod
    def get_or_create_conversation(db: Session, thread_id: Optional[str], user_id: str) -> Conversation:
        """Get existing conversation or create new one."""
        if thread_id:
            conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)
            if conversation:
                return conversation

        # Create new conversation
        return ConversationService.create_conversation(db, user_id)

    @staticmethod
    def add_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        return message

    @staticmethod
    def get_conversation_history(db: Session, thread_id: str, user_id: str) -> List[Message]:
        """Get all messages in a conversation."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if not conversation:
            return []

        return db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp).all()

    @staticmethod
    def list_conversations(db: Session, user_id: str, limit: int = 50) -> List[Conversation]:
        """List all conversations for a user."""
        return db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).limit(limit).all()

    @staticmethod
    def delete_conversation(db: Session, thread_id: str, user_id: str) -> bool:
        """Delete a conversation."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if not conversation:
            return False

        db.delete(conversation)
        db.commit()

        return True
