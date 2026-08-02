from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.config import settings
from typing import Optional, List
from datetime import datetime
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
        db.query(Conversation).filter(Conversation.id == conversation_id).update(
            {"updated_at": datetime.utcnow()}
        )
        db.commit()

        return message

    @staticmethod
    def get_conversation_history(
        db: Session,
        thread_id: str,
        user_id: str,
        limit: Optional[int] = None,
        since_reset: bool = True,
    ) -> List[Message]:
        """Recent messages of a conversation, oldest-first.

        Bounded on purpose. This used to load every message a thread had ever
        had, on every turn, and the callers trimmed the list in Python
        afterwards — so the cost was paid in full before anything was dropped.
        Permanent conversations cannot be archived or deleted, so their message
        count only ever grows, and the first thing to break was not memory but
        the turn itself: the assembled prompt eventually exceeded the model's
        context limit and that user's chat stayed broken until they reset it.

        The context-reset boundary is applied in SQL for the same reason —
        those rows are deliberately discarded, so there is no point loading
        them. `limit` overrides settings.chat_history_max_messages for callers
        that genuinely want a different window.

        `since_reset=False` keeps the messages before the last context reset.
        A reset is a chat-UX boundary — "start this conversation fresh" — not an
        instruction to forget that the messages happened, so callers summarising
        history rather than replaying it into a turn (the daily memory generator)
        must opt out or they silently lose part of the record.
        """
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if not conversation:
            return []

        max_messages = limit if limit is not None else settings.chat_history_max_messages

        query = db.query(Message).filter(Message.conversation_id == conversation.id)

        # Message.id is autoincrement, so "after the reset" is exact — the
        # positional slice the callers used could not disambiguate messages
        # sharing a timestamp.
        if since_reset:
            last_reset_id = (
                db.query(Message.id)
                .filter(
                    Message.conversation_id == conversation.id,
                    Message.source == "context_reset",
                )
                .order_by(Message.id.desc())
                .limit(1)
                .scalar()
            )
            if last_reset_id is not None:
                query = query.filter(Message.id > last_reset_id)

        # Newest-first + LIMIT to select the window, then flip back: the caller
        # contract is oldest-first. id breaks timestamp ties so the window is
        # deterministic.
        rows = (
            query.order_by(Message.timestamp.desc(), Message.id.desc())
            .limit(max_messages)
            .all()
        )
        rows.reverse()
        return rows

    @staticmethod
    def list_conversations(
        db: Session,
        user_id: str,
        limit: int = 199,
        offset: int = 0,
        archived: bool = False,
    ) -> tuple[List[Conversation], bool]:
        """List task conversations for a user with pagination.

        The permanent conversation is excluded — it is always returned separately
        by the API endpoint on the first page.

        Returns a (conversations, has_more) tuple.
        """
        rows = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.is_archived == archived,
            Conversation.type == "task",
        ).order_by(Conversation.updated_at.desc()).offset(offset).limit(limit + 1).all()

        has_more = len(rows) > limit
        return rows[:limit], has_more

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
    def count_user_messages(db: Session, conversation_id: int) -> int:
        return (
            db.query(func.count(Message.id))
            .filter(Message.conversation_id == conversation_id, Message.role == "user")
            .scalar()
            or 0
        )

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
    def list_activity_by_date(db: Session, user_id: str) -> List[dict]:
        """Count conversations with activity per calendar day for heatmap."""
        rows = (
            db.query(
                cast(Conversation.updated_at, Date).label("date"),
                func.count(Conversation.id).label("count"),
            )
            .filter(Conversation.user_id == user_id)
            .group_by(cast(Conversation.updated_at, Date))
            .all()
        )
        return [{"date": str(row.date), "count": row.count} for row in rows]

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
