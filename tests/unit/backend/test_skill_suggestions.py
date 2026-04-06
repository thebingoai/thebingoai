"""Tests for skill suggestion model, schema, detection, and evaluation."""

import backend.models.user_skill  # noqa: F401 — resolve relationship mapper

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.skill_suggestion import SkillSuggestion
from backend.schemas.skill import SkillSuggestionResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def suggestion_db():
    """In-memory SQLite with SkillSuggestion + dependency tables.

    SkillSuggestion uses JSONB (Postgres-only) so we create it via raw DDL.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
    ])

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE skill_suggestions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                suggested_name VARCHAR NOT NULL,
                suggested_description TEXT,
                suggested_skill_type VARCHAR(20) NOT NULL DEFAULT 'instruction',
                suggested_instructions TEXT,
                pattern_summary TEXT,
                source_conversation_ids TEXT,
                confidence FLOAT NOT NULL DEFAULT 0.0,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                recommendation VARCHAR(20),
                recommendation_reason TEXT,
                frequency_count INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def detection_db():
    """Extended DB for detection task tests — includes conversations + messages."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
    ])

    with engine.connect() as conn:
        # Conversations — skip partial index (postgresql_where)
        conn.execute(text("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id VARCHAR NOT NULL UNIQUE,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                title VARCHAR,
                type VARCHAR(20) NOT NULL DEFAULT 'task',
                is_archived BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        # Skill suggestions — skip JSONB
        conn.execute(text("""
            CREATE TABLE skill_suggestions (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                suggested_name VARCHAR NOT NULL,
                suggested_description TEXT,
                suggested_skill_type VARCHAR(20) NOT NULL DEFAULT 'instruction',
                suggested_instructions TEXT,
                pattern_summary TEXT,
                source_conversation_ids TEXT,
                confidence FLOAT NOT NULL DEFAULT 0.0,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                recommendation VARCHAR(20),
                recommendation_reason TEXT,
                frequency_count INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    # Messages + UserSkill via SQLAlchemy (no PG-only columns)
    Base.metadata.create_all(engine, tables=[Message.__table__])

    # UserSkill has JSONB too — create manually
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_skills (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL REFERENCES users(id),
                name VARCHAR NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                skill_type VARCHAR(20) DEFAULT 'code',
                prompt_template TEXT,
                code TEXT,
                instructions TEXT,
                activation_hint TEXT,
                parameters_schema TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                version INTEGER DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def user(suggestion_db):
    u = User(id="u-1", email="alice@test.com", auth_provider="supabase")
    suggestion_db.add(u)
    suggestion_db.commit()
    return u


@pytest.fixture
def detection_user(detection_db):
    u = User(id="u-det", email="det@test.com", auth_provider="supabase")
    detection_db.add(u)
    detection_db.commit()
    return u


def _seed_messages(db, user, count=15):
    """Create a conversation with N user messages for detection tests."""
    conv = Conversation(
        thread_id="thread-det-1",
        user_id=user.id,
        title="Test",
        type="task",
    )
    db.add(conv)
    db.flush()
    now = datetime.utcnow()
    for i in range(count):
        db.add(Message(
            conversation_id=conv.id,
            role="user",
            content=f"Show me regional sales for week {i}",
            timestamp=now - timedelta(days=count - i),
        ))
    db.commit()
    return conv


# ---------------------------------------------------------------------------
# Phase 1: Model new fields round-trip
# ---------------------------------------------------------------------------

class TestSkillSuggestionModel:
    """Verify the three new columns persist and round-trip correctly."""

    def test_new_fields_persist(self, suggestion_db, user):
        """Create a SkillSuggestion with evaluation fields, verify they round-trip."""
        s = SkillSuggestion(
            user_id=user.id,
            suggested_name="Weekly Sales Summary",
            suggested_description="Auto-format regional sales queries",
            suggested_skill_type="instruction",
            confidence=0.85,
            status="pending",
            recommendation="recommended",
            recommendation_reason="You asked about regional sales 12 times",
            frequency_count=12,
        )
        suggestion_db.add(s)
        suggestion_db.commit()

        fetched = suggestion_db.query(SkillSuggestion).filter_by(id=s.id).one()
        assert fetched.recommendation == "recommended"
        assert fetched.recommendation_reason == "You asked about regional sales 12 times"
        assert fetched.frequency_count == 12

    def test_new_fields_nullable(self, suggestion_db, user):
        """New fields default to None when not provided."""
        s = SkillSuggestion(
            user_id=user.id,
            suggested_name="Debug Logger",
            suggested_skill_type="code",
            confidence=0.7,
        )
        suggestion_db.add(s)
        suggestion_db.commit()

        fetched = suggestion_db.query(SkillSuggestion).filter_by(id=s.id).one()
        assert fetched.recommendation is None
        assert fetched.recommendation_reason is None
        assert fetched.frequency_count is None


# ---------------------------------------------------------------------------
# Phase 1: Schema serialization
# ---------------------------------------------------------------------------

class TestSkillSuggestionResponseSchema:
    """Verify SkillSuggestionResponse handles the new fields."""

    def test_schema_with_new_fields(self):
        """Schema accepts and serializes recommendation fields."""
        resp = SkillSuggestionResponse(
            id="s-1",
            suggested_name="Weekly Sales Summary",
            suggested_description="Auto-format queries",
            suggested_skill_type="instruction",
            pattern_summary="Regional sales every Monday",
            confidence=0.85,
            status="pending",
            recommendation="recommended",
            recommendation_reason="You asked 12 times",
            frequency_count=12,
            created_at=datetime(2026, 4, 6, tzinfo=timezone.utc),
        )
        assert resp.recommendation == "recommended"
        assert resp.recommendation_reason == "You asked 12 times"
        assert resp.frequency_count == 12

    def test_schema_with_none_fields(self):
        """Schema works when new fields are None (backward compat)."""
        resp = SkillSuggestionResponse(
            id="s-2",
            suggested_name="Debug Logger",
            suggested_skill_type="code",
            confidence=0.7,
            status="pending",
            created_at=datetime(2026, 4, 6, tzinfo=timezone.utc),
        )
        assert resp.recommendation is None
        assert resp.recommendation_reason is None
        assert resp.frequency_count is None

    def test_schema_dict_includes_new_fields(self):
        """model_dump() output includes the new fields."""
        resp = SkillSuggestionResponse(
            id="s-3",
            suggested_name="Test Skill",
            suggested_skill_type="instruction",
            confidence=0.8,
            status="pending",
            recommendation="low_value",
            recommendation_reason="Only used twice",
            frequency_count=2,
            created_at=datetime(2026, 4, 6, tzinfo=timezone.utc),
        )
        d = resp.model_dump()
        assert d["recommendation"] == "low_value"
        assert d["recommendation_reason"] == "Only used twice"
        assert d["frequency_count"] == 2


# ---------------------------------------------------------------------------
# Phase 2: Dismiss memory in detection
# ---------------------------------------------------------------------------

class TestDismissMemoryInDetection:
    """Verify dismissed suggestions are excluded from detection."""

    def _make_mock_provider(self, response_json):
        """Create a mock LLM provider that returns the given JSON string."""
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=json.dumps(response_json))
        return provider

    def test_prompt_contains_dismissed_patterns(self, detection_db, detection_user):
        """Dismissed suggestion names and patterns appear in the LLM prompt."""
        from backend.tasks.skill_detection_tasks import _process_user

        _seed_messages(detection_db, detection_user)

        # Add a dismissed suggestion
        detection_db.add(SkillSuggestion(
            id="dismissed-1",
            user_id=detection_user.id,
            suggested_name="weekly_report",
            suggested_skill_type="instruction",
            pattern_summary="Weekly sales report generation",
            confidence=0.8,
            status="dismissed",
        ))
        detection_db.commit()

        captured_prompt = {}
        provider = self._make_mock_provider([])

        async def capture_chat(messages, **kwargs):
            captured_prompt["text"] = messages[1]["content"]
            return "[]"

        provider.chat = AsyncMock(side_effect=capture_chat)

        cutoff = datetime.utcnow() - timedelta(days=14)
        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider):
            _process_user(detection_db, detection_user, cutoff)

        assert "weekly_report" in captured_prompt["text"]
        assert "Weekly sales report generation" in captured_prompt["text"]

    def test_dismissed_names_in_dedup_list(self, detection_db, detection_user):
        """A suggestion with the same name as a dismissed one is skipped."""
        from backend.tasks.skill_detection_tasks import _process_user

        _seed_messages(detection_db, detection_user)

        # Dismiss a suggestion
        detection_db.add(SkillSuggestion(
            id="dismissed-2",
            user_id=detection_user.id,
            suggested_name="regional_sales",
            suggested_skill_type="instruction",
            confidence=0.8,
            status="dismissed",
        ))
        detection_db.commit()

        # LLM returns a suggestion with the same name
        provider = self._make_mock_provider([{
            "suggested_name": "regional_sales",
            "suggested_description": "Same name as dismissed",
            "suggested_skill_type": "instruction",
            "pattern_summary": "test",
            "confidence": 0.9,
            "source_conversation_ids": [],
        }])

        cutoff = datetime.utcnow() - timedelta(days=14)
        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider):
            _process_user(detection_db, detection_user, cutoff)

        # Should not create a new pending suggestion
        pending = detection_db.query(SkillSuggestion).filter(
            SkillSuggestion.user_id == detection_user.id,
            SkillSuggestion.status == "pending",
        ).all()
        assert len(pending) == 0

    def test_no_dismissed_shows_none_in_prompt(self, detection_db, detection_user):
        """When no dismissed suggestions exist, prompt contains 'none'."""
        from backend.tasks.skill_detection_tasks import _process_user

        _seed_messages(detection_db, detection_user)

        captured_prompt = {}
        provider = MagicMock()

        async def capture_chat(messages, **kwargs):
            captured_prompt["text"] = messages[1]["content"]
            return "[]"

        provider.chat = AsyncMock(side_effect=capture_chat)

        cutoff = datetime.utcnow() - timedelta(days=14)
        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider):
            _process_user(detection_db, detection_user, cutoff)

        # The dismissed_patterns section should contain "none"
        assert "dismissed" in captured_prompt["text"].lower()
        # Find the section and verify it says "none"
        lines = captured_prompt["text"].split("\n")
        dismissed_idx = next(
            i for i, line in enumerate(lines) if "dismissed" in line.lower()
        )
        # The "none" should appear in the next line or same line
        section = "\n".join(lines[dismissed_idx:dismissed_idx + 2])
        assert "none" in section.lower()


# ---------------------------------------------------------------------------
# Phase 3: Evaluation pass
# ---------------------------------------------------------------------------

class TestEvaluationPass:
    """Verify the second LLM call evaluates suggestions."""

    def test_evaluate_updates_suggestion_fields(self, detection_db, detection_user):
        """_evaluate_suggestions calls LLM and updates recommendation fields."""
        from backend.tasks.skill_detection_tasks import _evaluate_suggestions

        s = SkillSuggestion(
            id="eval-1",
            user_id=detection_user.id,
            suggested_name="weekly_sales",
            suggested_description="Weekly sales query",
            suggested_skill_type="instruction",
            pattern_summary="Asked about sales weekly",
            confidence=0.85,
            status="pending",
        )
        detection_db.add(s)
        detection_db.commit()

        eval_response = json.dumps({
            "recommendation": "recommended",
            "recommendation_reason": "I'd recommend this — you asked 12 times",
            "frequency_count": 12,
        })
        provider = MagicMock()
        provider.chat = AsyncMock(return_value=eval_response)

        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider):
            _evaluate_suggestions(detection_db, detection_user, [s], message_count=50)

        detection_db.refresh(s)
        assert s.recommendation == "recommended"
        assert s.recommendation_reason == "I'd recommend this — you asked 12 times"
        assert s.frequency_count == 12

    def test_evaluate_handles_invalid_json(self, detection_db, detection_user):
        """Invalid JSON from evaluation LLM leaves fields as None."""
        from backend.tasks.skill_detection_tasks import _evaluate_suggestions

        s = SkillSuggestion(
            id="eval-2",
            user_id=detection_user.id,
            suggested_name="broken_eval",
            suggested_skill_type="instruction",
            confidence=0.8,
            status="pending",
        )
        detection_db.add(s)
        detection_db.commit()

        provider = MagicMock()
        provider.chat = AsyncMock(return_value="not valid json {{{")

        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider):
            _evaluate_suggestions(detection_db, detection_user, [s], message_count=30)

        detection_db.refresh(s)
        assert s.recommendation is None
        assert s.recommendation_reason is None
        assert s.frequency_count is None

    def test_evaluate_empty_list_no_llm_call(self, detection_db, detection_user):
        """No LLM call when suggestions list is empty."""
        from backend.tasks.skill_detection_tasks import _evaluate_suggestions

        provider = MagicMock()
        provider.chat = AsyncMock()

        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider):
            _evaluate_suggestions(detection_db, detection_user, [], message_count=30)

        provider.chat.assert_not_called()

    def test_process_user_creates_and_evaluates(self, detection_db, detection_user):
        """End-to-end: _process_user creates suggestions AND evaluates them."""
        from backend.tasks.skill_detection_tasks import _process_user

        _seed_messages(detection_db, detection_user)

        detection_json = json.dumps([{
            "suggested_name": "sales_summary",
            "suggested_description": "Summarize sales data",
            "suggested_skill_type": "instruction",
            "pattern_summary": "Weekly sales pattern",
            "confidence": 0.9,
            "source_conversation_ids": [],
        }])
        eval_json = json.dumps({
            "recommendation": "recommended",
            "recommendation_reason": "Strong recurring pattern",
            "frequency_count": 8,
        })

        call_count = {"n": 0}
        provider = MagicMock()

        async def multi_chat(messages, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return detection_json
            return eval_json

        provider.chat = AsyncMock(side_effect=multi_chat)

        cutoff = datetime.utcnow() - timedelta(days=14)
        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider), \
             patch("backend.tasks.skill_detection_tasks._notify_new_suggestions"):
            _process_user(detection_db, detection_user, cutoff)

        # Should have called LLM twice: detection + evaluation
        assert call_count["n"] == 2

        # Suggestion should exist with evaluation fields
        s = detection_db.query(SkillSuggestion).filter(
            SkillSuggestion.user_id == detection_user.id,
            SkillSuggestion.status == "pending",
        ).one()
        assert s.suggested_name == "sales_summary"
        assert s.recommendation == "recommended"
        assert s.frequency_count == 8


# ---------------------------------------------------------------------------
# Phase 4: WebSocket push
# ---------------------------------------------------------------------------

class TestWebSocketPush:
    """Verify WS push after evaluation."""

    def test_notify_calls_publish_with_correct_payload(self):
        """_notify_new_suggestions calls ConnectionManager.publish_to_user_sync."""
        from backend.tasks.skill_detection_tasks import _notify_new_suggestions

        s = MagicMock()
        s.id = "s-1"
        s.suggested_name = "weekly_sales"
        s.suggested_description = "Sales summary"
        s.suggested_skill_type = "instruction"
        s.pattern_summary = "Weekly pattern"
        s.confidence = 0.9
        s.status = "pending"
        s.recommendation = "recommended"
        s.recommendation_reason = "Strong pattern"
        s.frequency_count = 12

        with patch("backend.services.ws_connection_manager.ConnectionManager.publish_to_user_sync") as mock_pub:
            _notify_new_suggestions("user-1", [s])

        mock_pub.assert_called_once()
        call_args = mock_pub.call_args
        assert call_args[0][0] == "user-1"
        payload = call_args[0][1]
        assert payload["type"] == "skill_suggestions.new"
        assert len(payload["suggestions"]) == 1
        assert payload["suggestions"][0]["id"] == "s-1"
        assert payload["suggestions"][0]["recommendation"] == "recommended"
        assert payload["suggestions"][0]["frequency_count"] == 12

    def test_process_user_publishes_after_evaluation(self, detection_db, detection_user):
        """End-to-end: _process_user calls WS publish after evaluation."""
        from backend.tasks.skill_detection_tasks import _process_user

        _seed_messages(detection_db, detection_user)

        detection_json = json.dumps([{
            "suggested_name": "ws_test_skill",
            "suggested_description": "Test skill",
            "suggested_skill_type": "instruction",
            "pattern_summary": "Test pattern",
            "confidence": 0.9,
            "source_conversation_ids": [],
        }])
        eval_json = json.dumps({
            "recommendation": "recommended",
            "recommendation_reason": "Strong pattern",
            "frequency_count": 10,
        })

        call_count = {"n": 0}
        provider = MagicMock()

        async def multi_chat(messages, **kwargs):
            call_count["n"] += 1
            return detection_json if call_count["n"] == 1 else eval_json

        provider.chat = AsyncMock(side_effect=multi_chat)

        cutoff = datetime.utcnow() - timedelta(days=14)
        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider), \
             patch("backend.services.ws_connection_manager.ConnectionManager.publish_to_user_sync") as mock_pub:
            _process_user(detection_db, detection_user, cutoff)

        mock_pub.assert_called_once()
        payload = mock_pub.call_args[0][1]
        assert payload["type"] == "skill_suggestions.new"
        assert payload["suggestions"][0]["suggested_name"] == "ws_test_skill"

    def test_no_publish_when_zero_suggestions(self, detection_db, detection_user):
        """No WS publish when detection creates zero suggestions."""
        from backend.tasks.skill_detection_tasks import _process_user

        _seed_messages(detection_db, detection_user)

        provider = MagicMock()
        provider.chat = AsyncMock(return_value="[]")

        cutoff = datetime.utcnow() - timedelta(days=14)
        with patch("backend.tasks.skill_detection_tasks.get_provider", return_value=provider), \
             patch("backend.services.ws_connection_manager.ConnectionManager.publish_to_user_sync") as mock_pub:
            _process_user(detection_db, detection_user, cutoff)

        mock_pub.assert_not_called()
