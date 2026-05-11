"""End-to-end: POST /dashboards/{id}/brief -> orchestrator (stubbed) -> emit_briefing -> row + message + WS event."""

import uuid
from unittest.mock import patch

from backend.models.briefing import Briefing
from backend.models.message import Message
from backend.models.conversation import Conversation


def test_post_brief_runs_through_to_ready(
    authenticated_client, db_session, sample_dashboard, sample_user
):
    """
    Full briefing roundtrip with a stubbed orchestrator.

    Patches the Celery generate_briefing task so .delay() runs synchronously
    inside the test process.  The stubbed orchestrator directly sets the
    briefing status to 'ready', persists the payload, inserts an assistant
    Message, and fires a WebSocket event — all against the same test database
    session so the assertions below see the committed state.
    """
    ws_events: list = []

    # ------------------------------------------------------------------
    # Stub that replaces the Celery worker
    # ------------------------------------------------------------------
    def run_fake_orchestrator_sync(briefing_id: int) -> None:
        """Replicate what emit_briefing does inside the orchestrator tool."""
        briefing = (
            db_session.query(Briefing)
            .filter(Briefing.id == briefing_id)
            .first()
        )
        assert briefing is not None, f"Briefing {briefing_id} not found"

        briefing.payload = {
            "headline": "Roundtrip headline",
            "deck": "Roundtrip deck.",
            "kpis": [{"label": "X", "value": "1"}],
            "sections": [{"heading": "1. one", "prose": "p"}],
            "key_takeaways": ["a", "b", "c"],
        }
        briefing.status = "ready"
        briefing.error = None

        # --- _post_chat_message equivalent (inline, same db_session) ---
        conv = (
            db_session.query(Conversation)
            .filter(
                Conversation.user_id == sample_user.id,
                Conversation.kind == "assistant",
            )
            .first()
        )
        if not conv:
            conv = Conversation(
                user_id=sample_user.id,
                thread_id=str(uuid.uuid4()),
                title="Assistant",
                kind="assistant",
                type="task",
            )
            db_session.add(conv)
            db_session.flush()

        msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content="Roundtrip headline",
            source="heartbeat",
            briefing_id=briefing_id,
        )
        db_session.add(msg)
        db_session.commit()

        # --- _emit_ws equivalent (captured for assertion) ---
        ws_events.append((sample_user.id, briefing_id))

    # ------------------------------------------------------------------
    # Patch celery task so .delay() runs inline
    # ------------------------------------------------------------------
    with patch("backend.api.briefings.generate_briefing") as celery_mock:
        celery_mock.delay.side_effect = run_fake_orchestrator_sync

        resp = authenticated_client.post(
            f"/api/dashboards/{sample_dashboard.id}/brief"
        )
        assert resp.status_code == 202, resp.text
        bid = resp.json()["briefing_id"]

    # ------------------------------------------------------------------
    # Assertions — re-read from DB to confirm everything was persisted
    # ------------------------------------------------------------------
    db_session.expire_all()

    briefing = db_session.query(Briefing).filter(Briefing.id == bid).one()
    assert briefing.status == "ready"
    assert briefing.payload["headline"] == "Roundtrip headline"
    assert len(briefing.payload["sections"]) == 1
    assert len(briefing.payload["key_takeaways"]) == 3

    msg = (
        db_session.query(Message)
        .filter(Message.briefing_id == bid)
        .first()
    )
    assert msg is not None
    assert msg.content == "Roundtrip headline"
    assert msg.role == "assistant"
    assert msg.source == "heartbeat"

    conv = (
        db_session.query(Conversation)
        .filter(Conversation.id == msg.conversation_id)
        .one()
    )
    assert conv.user_id == sample_user.id
    assert conv.kind == "assistant"

    # WS event should have been emitted exactly once
    assert ws_events == [(sample_user.id, bid)]
