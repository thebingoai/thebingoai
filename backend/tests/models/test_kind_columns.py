from backend.models.conversation import Conversation
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.message import Message


def test_conversation_has_kind():
    assert "kind" in {c.name for c in Conversation.__table__.columns}

def test_heartbeat_job_has_kind():
    assert "kind" in {c.name for c in HeartbeatJob.__table__.columns}

def test_message_has_briefing_id():
    assert "briefing_id" in {c.name for c in Message.__table__.columns}
