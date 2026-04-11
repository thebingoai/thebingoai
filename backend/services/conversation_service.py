from sqlalchemy import case
from sqlalchemy.orm import Session
from backend.models.conversation import Conversation
from backend.models.message import Message
from typing import Optional, List
import uuid


class ConversationService:
    """Service for managing conversations and messages."""

    @staticmethod
    def create_conversation(
        db: Session,
        user_id: str,
        title: Optional[str] = None,
        conv_type: str = "task",
    ) -> Conversation:
        """Create a new conversation."""
        thread_id = str(uuid.uuid4())

        conversation = Conversation(
            thread_id=thread_id,
            user_id=user_id,
            title=title or ("New Task" if conv_type == "task" else "Bingo AI"),
            type=conv_type,
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation

    @staticmethod
    def get_permanent_conversation(db: Session, user_id: str) -> Optional[Conversation]:
        """Return the user's permanent conversation, or None if not yet created."""
        return db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.type == "permanent",
        ).first()

    @staticmethod
    def get_or_create_permanent_conversation(db: Session, user_id: str) -> Conversation:
        """Return the user's permanent conversation, creating it if it doesn't exist."""
        conv = ConversationService.get_permanent_conversation(db, user_id)
        if conv:
            return conv
        return ConversationService.create_conversation(
            db, user_id, title="Bingo AI", conv_type="permanent"
        )

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
    def add_message(
        db: Session,
        conversation_id: int,
        role: str,
        content: str,
        attachments: Optional[list] = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            attachments=attachments,
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
    def list_conversations(db: Session, user_id: str, limit: int = 50, archived: bool = False) -> List[Conversation]:
        """List conversations for a user, filtered by archive status.

        The permanent conversation is always sorted first so it is never
        pushed out of the result by the limit, regardless of its age.
        """
        return db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.is_archived == archived,
        ).order_by(
            case((Conversation.type == "permanent", 0), else_=1),
            Conversation.updated_at.desc(),
        ).limit(limit).all()

    @staticmethod
    def archive_conversation(db: Session, thread_id: str, user_id: str, archived: bool = True) -> Conversation:
        """Archive or unarchive a conversation. Raises ValueError for permanent conversations."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)
        if not conversation:
            raise LookupError("Conversation not found")
        if conversation.type == "permanent":
            raise ValueError("Cannot archive the permanent conversation")
        conversation.is_archived = archived
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def update_title(db: Session, conversation_id: int, title: str) -> None:
        """Update the title of a conversation."""
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation:
            conversation.title = title
            db.commit()

    @staticmethod
    def add_context_reset(db: Session, conversation_id: int) -> Message:
        """Insert a context reset marker into a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role="system",
            content="",
            source="context_reset",
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def delete_conversation(db: Session, thread_id: str, user_id: str) -> bool:
        """Delete a conversation. Returns False if not found, raises ValueError for permanent."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if not conversation:
            return False

        if conversation.type == "permanent":
            raise ValueError("Cannot delete the permanent conversation")

        db.delete(conversation)
        db.commit()

        return True
