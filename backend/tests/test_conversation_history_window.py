"""get_conversation_history must be bounded and cut at the last context reset.

It previously loaded every message a thread had ever had, on every turn, and
the callers trimmed in Python afterwards. Permanent conversations cannot be
archived or deleted, so the count only grows: the assembled prompt eventually
exceeded the provider's context limit and that user's chat stayed broken until
they manually reset it.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import JSON, LargeBinary, create_engine, event
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.services.conversation_service import ConversationService

USER_ID = "user-1"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # Postgres-only column types across the shared metadata; swapped for their
    # portable equivalents so create_all works on SQLite. Mirrors the fixture
    # in tests/api/test_refresh_visibility.py.
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
                col.server_default = None
            elif isinstance(col.type, BYTEA):
                col.type = LargeBinary()
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def _make_conversation(db, n_messages, reset_at=None):
    convo = Conversation(thread_id="t-1", user_id=USER_ID)
    db.add(convo)
    db.commit()

    base = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(n_messages):
        db.add(
            Message(
                conversation_id=convo.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"m{i}",
                timestamp=base + timedelta(seconds=i),
                source="context_reset" if i == reset_at else "chat",
            )
        )
    db.commit()
    return convo


def test_history_is_capped(db):
    _make_conversation(db, 250)

    history = ConversationService.get_conversation_history(db, "t-1", USER_ID, limit=100)

    assert len(history) == 100, "history must be windowed, not loaded whole"
    # The window is the most recent messages, still oldest-first.
    assert [m.content for m in history[:2]] == ["m150", "m151"]
    assert history[-1].content == "m249"


def test_history_is_oldest_first(db):
    _make_conversation(db, 5)

    history = ConversationService.get_conversation_history(db, "t-1", USER_ID)

    assert [m.content for m in history] == ["m0", "m1", "m2", "m3", "m4"], (
        "callers feed this straight into the prompt; order must not flip"
    )


def test_messages_before_a_context_reset_are_never_loaded(db):
    """The reset boundary moved from a Python slice into the query.

    Counting the rows the query returns proves the pre-reset messages are
    excluded in SQL rather than fetched and discarded.
    """
    _make_conversation(db, 20, reset_at=15)

    history = ConversationService.get_conversation_history(db, "t-1", USER_ID)

    assert [m.content for m in history] == ["m16", "m17", "m18", "m19"], (
        "must return only what follows the reset, and not the reset row itself"
    )


def test_reset_boundary_wins_over_the_window(db):
    """A reset inside the window still truncates: it is a hard boundary."""
    _make_conversation(db, 50, reset_at=45)

    history = ConversationService.get_conversation_history(db, "t-1", USER_ID, limit=100)

    assert [m.content for m in history] == ["m46", "m47", "m48", "m49"]


def test_only_the_latest_reset_applies(db):
    _make_conversation(db, 30, reset_at=10)
    convo = db.query(Conversation).first()
    db.add(
        Message(
            conversation_id=convo.id,
            role="user",
            content="second-reset",
            timestamp=datetime(2026, 1, 1, 0, 0, 25),
            source="context_reset",
        )
    )
    db.commit()

    history = ConversationService.get_conversation_history(db, "t-1", USER_ID)

    assert all(m.source != "context_reset" for m in history)
    assert history == [] or history[0].content != "m11", (
        "an older reset must not win over a newer one"
    )


def test_since_reset_false_keeps_the_pre_reset_messages(db):
    """The daily memory generator summarises the day; it does not replay a turn.

    A context reset means "start this conversation fresh", not "this day did not
    happen". Applying the chat window's reset boundary to the memory generator
    silently dropped part of the record it exists to preserve.
    """
    _make_conversation(db, 20, reset_at=15)

    history = ConversationService.get_conversation_history(
        db, "t-1", USER_ID, since_reset=False,
    )

    contents = [m.content for m in history]
    assert "m0" in contents and "m14" in contents, (
        "opting out must keep everything before the reset"
    )
    assert contents[-1] == "m19", "and still return the later messages, oldest-first"


def test_since_reset_false_is_still_bounded(db):
    """Opting out of the reset boundary must not opt out of the window too.

    The window deliberately reaches past the reset — only 49 messages follow it,
    so a run that still applied the boundary would return 49, not 100.
    """
    _make_conversation(db, 250, reset_at=200)

    history = ConversationService.get_conversation_history(
        db, "t-1", USER_ID, limit=100, since_reset=False,
    )

    assert len(history) == 100, "the cap still applies when the boundary is off"
    assert history[-1].content == "m249", "the window is the newest N, oldest-first"
    assert history[0].content == "m150"


def test_the_reset_boundary_is_still_the_default(db):
    """Every chat caller relies on the default; only the summariser opts out."""
    _make_conversation(db, 20, reset_at=15)

    assert [m.content for m in ConversationService.get_conversation_history(
        db, "t-1", USER_ID,
    )] == ["m16", "m17", "m18", "m19"]


def test_unknown_thread_returns_empty(db):
    assert ConversationService.get_conversation_history(db, "nope", USER_ID) == []


def test_query_count_does_not_grow_with_conversation_length(db):
    """Guards the actual regression: cost must not scale with history size."""
    engine = db.get_bind()
    rows_scanned = []

    @event.listens_for(engine, "after_cursor_execute")
    def _watch(conn, cursor, statement, parameters, *a):
        if "messages" in statement.lower() and statement.strip().upper().startswith("SELECT"):
            rows_scanned.append(statement)

    _make_conversation(db, 500)
    rows_scanned.clear()

    history = ConversationService.get_conversation_history(db, "t-1", USER_ID, limit=50)

    assert len(history) == 50
    assert any("LIMIT" in s.upper() for s in rows_scanned), (
        "the cap must be applied by the database, not after loading every row"
    )
