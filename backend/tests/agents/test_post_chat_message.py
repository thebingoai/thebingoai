"""
Unit tests for _post_chat_message in orchestrator_briefing_tool.

Verifies that briefing messages are posted to the user's permanent
conversation (type='permanent') — never to a new task/assistant thread.
"""
import uuid
import pytest

from backend.agents.orchestrator.orchestrator_briefing_tool import _post_chat_message
from backend.models.briefing import Briefing
from backend.models.conversation import Conversation
from backend.models.message import Message


def _make_briefing(db, user, dashboard):
    """Create a minimal ready Briefing row and return its id."""
    b = Briefing(
        user_id=user.id,
        dashboard_id=dashboard.id,
        source="scheduled",
        status="ready",
    )
    db.add(b)
    db.flush()
    return b.id


def test_posts_to_permanent_conversation(db_session, sample_user, sample_dashboard):
    """Message lands in the user's existing permanent conversation."""
    perm = Conversation(
        user_id=sample_user.id,
        thread_id=str(uuid.uuid4()),
        title="Bingo AI",
        type="permanent",
        kind="chat",
    )
    db_session.add(perm)
    db_session.flush()

    bid = _make_briefing(db_session, sample_user, sample_dashboard)
    _post_chat_message(db_session, user_id=sample_user.id, briefing_id=bid, headline="Test headline")
    db_session.commit()

    msg = db_session.query(Message).filter(
        Message.conversation_id == perm.id,
        Message.briefing_id == bid,
    ).first()
    assert msg is not None
    assert msg.role == "assistant"
    assert msg.source == "heartbeat"
    assert msg.content == "Test headline"


def test_creates_permanent_conversation_when_none_exists(db_session, sample_user, sample_dashboard):
    """If no permanent conversation exists yet, one is created — not a task thread."""
    bid = _make_briefing(db_session, sample_user, sample_dashboard)
    _post_chat_message(db_session, user_id=sample_user.id, briefing_id=bid, headline="Auto-created conv")
    db_session.commit()

    conv = db_session.query(Conversation).filter(
        Conversation.user_id == sample_user.id,
        Conversation.type == "permanent",
    ).first()
    assert conv is not None, "permanent conversation should have been created"

    task_convs = db_session.query(Conversation).filter(
        Conversation.user_id == sample_user.id,
        Conversation.type == "task",
    ).count()
    assert task_convs == 0, "no task conversation should have been created"

    msg = db_session.query(Message).filter(
        Message.conversation_id == conv.id,
        Message.briefing_id == bid,
    ).first()
    assert msg is not None


def test_never_creates_rogue_assistant_kind_conversation(db_session, sample_user, sample_dashboard):
    """Even without a permanent conv, kind='assistant' task threads must not appear."""
    bid = _make_briefing(db_session, sample_user, sample_dashboard)
    _post_chat_message(db_session, user_id=sample_user.id, briefing_id=bid, headline="No rogue")
    db_session.commit()

    rogue = db_session.query(Conversation).filter(
        Conversation.user_id == sample_user.id,
        Conversation.kind == "assistant",
    ).count()
    assert rogue == 0, "no kind='assistant' conversation should be created"


def test_second_briefing_reuses_same_permanent_conversation(db_session, sample_user, sample_dashboard):
    """Two briefings for the same user go to the same permanent conversation."""
    bid1 = _make_briefing(db_session, sample_user, sample_dashboard)
    bid2 = _make_briefing(db_session, sample_user, sample_dashboard)

    _post_chat_message(db_session, user_id=sample_user.id, briefing_id=bid1, headline="First")
    _post_chat_message(db_session, user_id=sample_user.id, briefing_id=bid2, headline="Second")
    db_session.commit()

    convs = db_session.query(Conversation).filter(
        Conversation.user_id == sample_user.id,
        Conversation.type == "permanent",
    ).all()
    assert len(convs) == 1, "only one permanent conversation should exist"

    msgs = db_session.query(Message).filter(
        Message.conversation_id == convs[0].id,
        Message.source == "heartbeat",
    ).all()
    assert len(msgs) == 2
    assert {m.briefing_id for m in msgs} == {bid1, bid2}
