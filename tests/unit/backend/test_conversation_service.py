"""Tests for the conversation CRUD service."""

import backend.models.user_skill  # noqa: F401 — resolve relationship mapper

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.agent_step import AgentStep
from backend.models.message import Message
from backend.services.conversation_service import ConversationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conv_db():
    """In-memory SQLite with all tables needed by ConversationService.

    The real Conversation model has a partial unique index using
    postgresql_where which SQLite turns into a full unique constraint
    on user_id.  We create the tables via raw DDL to avoid that.
    """
    engine = create_engine("sqlite:///:memory:")

    # Create dependency tables via SQLAlchemy (these have no PG-only features)
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        HeartbeatJob.__table__,
    ])

    # Create conversations table manually to skip the problematic partial index
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id VARCHAR NOT NULL UNIQUE,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                title VARCHAR,
                type VARCHAR(20) NOT NULL DEFAULT 'task',
                is_archived BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        conn.commit()

    # Create messages and agent_steps via SQLAlchemy
    Base.metadata.create_all(engine, tables=[
        Message.__table__,
        AgentStep.__table__,
    ])

    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(conv_db):
    """Create a test user for conversation tests."""
    u = User(id="u-1", email="alice@test.com", auth_provider="supabase")
    conv_db.add(u)
    conv_db.commit()
    return u


# ---------------------------------------------------------------------------
# create_conversation
# ---------------------------------------------------------------------------

class TestCreateConversation:
    """Tests for ConversationService.create_conversation."""

    def test_returns_conversation_object(self, conv_db, user):
        """Creating a conversation returns a Conversation instance."""
        conv = ConversationService.create_conversation(conv_db, user.id)
        assert isinstance(conv, Conversation)
        assert conv.id is not None

    def test_default_title_is_new_task(self, conv_db, user):
        """Default title for task conversations is 'New Task'."""
        conv = ConversationService.create_conversation(conv_db, user.id)
        assert conv.title == "New Task"

    def test_permanent_type_default_title(self, conv_db, user):
        """Permanent conversations default to 'Bingo AI' title."""
        conv = ConversationService.create_conversation(conv_db, user.id, conv_type="permanent")
        assert conv.title == "Bingo AI"

    def test_custom_title(self, conv_db, user):
        """Explicit title overrides the default."""
        conv = ConversationService.create_conversation(conv_db, user.id, title="My Chat")
        assert conv.title == "My Chat"


# ---------------------------------------------------------------------------
# get_permanent_conversation
# ---------------------------------------------------------------------------

class TestGetPermanentConversation:
    """Tests for get_permanent_conversation."""

    def test_returns_none_when_no_permanent(self, conv_db, user):
        """Returns None when user has no permanent conversation."""
        result = ConversationService.get_permanent_conversation(conv_db, user.id)
        assert result is None

    def test_finds_permanent_conversation(self, conv_db, user):
        """Returns the permanent conversation when one exists."""
        ConversationService.create_conversation(conv_db, user.id, conv_type="permanent")
        result = ConversationService.get_permanent_conversation(conv_db, user.id)
        assert result is not None
        assert result.type == "permanent"


# ---------------------------------------------------------------------------
# get_or_create_permanent_conversation
# ---------------------------------------------------------------------------

class TestGetOrCreatePermanentConversation:
    """Tests for get_or_create_permanent_conversation."""

    def test_creates_if_missing(self, conv_db, user):
        """Creates a new permanent conversation when none exists."""
        conv = ConversationService.get_or_create_permanent_conversation(conv_db, user.id)
        assert conv.type == "permanent"
        assert conv.title == "Bingo AI"

    def test_returns_existing(self, conv_db, user):
        """Returns the existing permanent conversation on second call."""
        first = ConversationService.get_or_create_permanent_conversation(conv_db, user.id)
        second = ConversationService.get_or_create_permanent_conversation(conv_db, user.id)
        assert first.id == second.id


# ---------------------------------------------------------------------------
# add_message / get_conversation_history
# ---------------------------------------------------------------------------

class TestMessages:
    """Tests for add_message and get_conversation_history."""

    def test_add_message_creates_message(self, conv_db, user):
        """add_message persists a message and returns it."""
        conv = ConversationService.create_conversation(conv_db, user.id)
        msg = ConversationService.add_message(conv_db, conv.id, "user", "Hello!")
        assert isinstance(msg, Message)
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.conversation_id == conv.id

    def test_get_conversation_history_returns_messages(self, conv_db, user):
        """get_conversation_history returns all messages for a conversation."""
        conv = ConversationService.create_conversation(conv_db, user.id)
        ConversationService.add_message(conv_db, conv.id, "user", "Hi")
        ConversationService.add_message(conv_db, conv.id, "assistant", "Hello!")

        messages = ConversationService.get_conversation_history(conv_db, conv.thread_id, user.id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_get_history_returns_empty_for_unknown_thread(self, conv_db, user):
        """get_conversation_history returns [] for a non-existent thread."""
        messages = ConversationService.get_conversation_history(conv_db, "no-such-thread", user.id)
        assert messages == []


# ---------------------------------------------------------------------------
# list_conversations
# ---------------------------------------------------------------------------

class TestListConversations:
    """Tests for list_conversations."""

    def test_returns_user_conversations(self, conv_db, user):
        """list_conversations returns task conversations belonging to the user."""
        ConversationService.create_conversation(conv_db, user.id, title="A")
        ConversationService.create_conversation(conv_db, user.id, title="B")

        convs, _ = ConversationService.list_conversations(conv_db, user.id)
        assert len(convs) == 2

    def test_excludes_archived_by_default(self, conv_db, user):
        """list_conversations excludes archived conversations by default."""
        conv = ConversationService.create_conversation(conv_db, user.id, title="Will Archive")
        ConversationService.archive_conversation(conv_db, conv.thread_id, user.id)

        convs, _ = ConversationService.list_conversations(conv_db, user.id)
        assert len(convs) == 0

    def test_includes_archived_when_requested(self, conv_db, user):
        """list_conversations includes archived conversations when archived=True."""
        conv = ConversationService.create_conversation(conv_db, user.id, title="Archived")
        ConversationService.archive_conversation(conv_db, conv.thread_id, user.id)

        convs, _ = ConversationService.list_conversations(conv_db, user.id, archived=True)
        assert len(convs) == 1

    def test_excludes_permanent_from_list(self, conv_db, user):
        """list_conversations never includes the permanent conversation."""
        ConversationService.create_conversation(conv_db, user.id, conv_type="permanent")
        ConversationService.create_conversation(conv_db, user.id, title="Task A")
        ConversationService.create_conversation(conv_db, user.id, title="Task B")

        convs, _ = ConversationService.list_conversations(conv_db, user.id)
        assert len(convs) == 2
        assert all(c.type == "task" for c in convs)

    def test_returns_has_more_false_when_under_limit(self, conv_db, user):
        """has_more is False when fewer rows exist than the limit."""
        for i in range(3):
            ConversationService.create_conversation(conv_db, user.id, title=f"T{i}")

        convs, has_more = ConversationService.list_conversations(conv_db, user.id, limit=5)
        assert len(convs) == 3
        assert has_more is False

    def test_returns_has_more_true_when_over_limit(self, conv_db, user):
        """has_more is True when more rows exist than the limit."""
        for i in range(5):
            ConversationService.create_conversation(conv_db, user.id, title=f"T{i}")

        convs, has_more = ConversationService.list_conversations(conv_db, user.id, limit=3)
        assert len(convs) == 3
        assert has_more is True

    def test_offset_skips_conversations(self, conv_db, user):
        """offset skips the specified number of rows."""
        for i in range(5):
            ConversationService.create_conversation(conv_db, user.id, title=f"T{i}")

        convs, _ = ConversationService.list_conversations(conv_db, user.id, limit=10, offset=2)
        assert len(convs) == 3

    def test_offset_and_limit_paginate(self, conv_db, user):
        """offset + limit produce correct pages across the full dataset."""
        for i in range(10):
            ConversationService.create_conversation(conv_db, user.id, title=f"T{i}")

        page1, has_more1 = ConversationService.list_conversations(conv_db, user.id, limit=3, offset=0)
        assert len(page1) == 3
        assert has_more1 is True

        page2, has_more2 = ConversationService.list_conversations(conv_db, user.id, limit=3, offset=3)
        assert len(page2) == 3
        assert has_more2 is True

        page4, has_more4 = ConversationService.list_conversations(conv_db, user.id, limit=3, offset=9)
        assert len(page4) == 1
        assert has_more4 is False

    def test_default_limit_is_199(self, conv_db, user):
        """Default limit is 199 — basic smoke test that it doesn't crash."""
        ConversationService.create_conversation(conv_db, user.id, title="A")
        ConversationService.create_conversation(conv_db, user.id, title="B")

        convs, has_more = ConversationService.list_conversations(conv_db, user.id)
        assert len(convs) == 2
        assert has_more is False


# ---------------------------------------------------------------------------
# archive / delete
# ---------------------------------------------------------------------------

class TestArchiveAndDelete:
    """Tests for archive and delete operations."""

    def test_archive_permanent_raises(self, conv_db, user):
        """Archiving a permanent conversation raises ValueError."""
        conv = ConversationService.create_conversation(conv_db, user.id, conv_type="permanent")
        with pytest.raises(ValueError, match="Cannot archive the permanent conversation"):
            ConversationService.archive_conversation(conv_db, conv.thread_id, user.id)

    def test_delete_permanent_raises(self, conv_db, user):
        """Deleting a permanent conversation raises ValueError."""
        conv = ConversationService.create_conversation(conv_db, user.id, conv_type="permanent")
        with pytest.raises(ValueError, match="Cannot delete the permanent conversation"):
            ConversationService.delete_conversation(conv_db, conv.thread_id, user.id)

    def test_delete_returns_false_for_missing(self, conv_db, user):
        """delete_conversation returns False when thread doesn't exist."""
        result = ConversationService.delete_conversation(conv_db, "ghost", user.id)
        assert result is False
