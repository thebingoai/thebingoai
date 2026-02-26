"""Celery task for detecting repeated user patterns and suggesting skills."""

from celery import shared_task
from backend.database.session import SessionLocal
from backend.models.user import User
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.models.user_skill import UserSkill
from backend.models.skill_suggestion import SkillSuggestion
from backend.llm.factory import get_provider
from backend.config import settings
from datetime import datetime, timedelta
import json
import uuid
import logging

logger = logging.getLogger(__name__)

_DETECTION_PROMPT = """Analyze these user messages and identify repeated patterns that could become reusable skills.

User messages:
{messages}

Existing skills (do NOT suggest skills that overlap these):
{existing_skills}

For each pattern, return a JSON array with objects:
{{
  "suggested_name": "snake_case_name",
  "suggested_description": "What this skill does",
  "suggested_skill_type": "instruction" | "code" | "prompt",
  "suggested_instructions": "Draft Markdown instructions for the skill",
  "pattern_summary": "1-2 sentences explaining the repeated pattern",
  "confidence": 0.0-1.0,
  "source_conversation_ids": ["conv_id_1", "conv_id_2"]
}}

Rules:
- Only return patterns with confidence >= 0.7
- Only suggest genuinely repeated patterns (seen 3+ times)
- Do not suggest skills that overlap existing skill names
- Return an empty array [] if no patterns qualify
- Return ONLY valid JSON, no other text"""


@shared_task(name="detect_skill_patterns")
def detect_skill_patterns():
    """
    Scan recent user messages for repeated patterns and create SkillSuggestion records.

    Runs every 6 hours via Celery Beat.
    """
    db = SessionLocal()

    try:
        users = db.query(User).all()
        cutoff = datetime.utcnow() - timedelta(days=14)

        for user in users:
            try:
                _process_user(db, user, cutoff)
            except Exception as e:
                logger.error(f"Skill detection failed for user {user.id}: {e}")

    finally:
        db.close()


def _process_user(db, user, cutoff: datetime):
    """Detect skill patterns for a single user."""
    # Count user messages in period
    message_count = db.query(Message).join(Conversation).filter(
        Conversation.user_id == user.id,
        Message.role == "user",
        Message.timestamp >= cutoff,
    ).count()

    if message_count < 10:
        logger.info(f"Skipping user {user.id}: only {message_count} messages in period")
        return

    # Skip users who already have 3+ pending suggestions
    pending_count = db.query(SkillSuggestion).filter(
        SkillSuggestion.user_id == user.id,
        SkillSuggestion.status == "pending",
    ).count()

    if pending_count >= 3:
        logger.info(f"Skipping user {user.id}: already has {pending_count} pending suggestions")
        return

    # Load user messages grouped by conversation
    rows = (
        db.query(Message.content, Conversation.thread_id)
        .join(Conversation)
        .filter(
            Conversation.user_id == user.id,
            Message.role == "user",
            Message.timestamp >= cutoff,
        )
        .order_by(Message.timestamp.asc())
        .limit(200)
        .all()
    )

    if not rows:
        return

    # Format messages for analysis
    messages_text = "\n".join(
        f"[{thread_id[:8]}] {content[:300]}"
        for content, thread_id in rows
    )

    # Load existing skill names to avoid overlap
    existing_skills = db.query(UserSkill.name).filter(
        UserSkill.user_id == user.id,
        UserSkill.is_active == True,
    ).all()
    existing_names = [s.name for s in existing_skills]

    # Load existing pending suggestion names
    pending_names = db.query(SkillSuggestion.suggested_name).filter(
        SkillSuggestion.user_id == user.id,
        SkillSuggestion.status == "pending",
    ).all()
    all_existing = existing_names + [s.suggested_name for s in pending_names]

    # Call LLM for pattern analysis
    try:
        provider = get_provider(settings.default_llm_provider)
        import asyncio

        async def _analyze():
            prompt = _DETECTION_PROMPT.format(
                messages=messages_text,
                existing_skills=", ".join(all_existing) if all_existing else "none",
            )
            return await provider.chat(
                [
                    {"role": "system", "content": "You are a skill pattern analyzer. Return only valid JSON arrays."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

        response = asyncio.run(_analyze())
    except Exception as e:
        logger.error(f"LLM analysis failed for user {user.id}: {e}")
        return

    # Parse suggestions
    try:
        text = response.strip()
        # Handle possible markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        patterns = json.loads(text)
        if not isinstance(patterns, list):
            return
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse LLM pattern response for user {user.id}: {e}")
        return

    created = 0
    for pattern in patterns:
        name = pattern.get("suggested_name", "")
        confidence = float(pattern.get("confidence", 0))

        if not name or confidence < 0.7:
            continue

        # Dedup against existing and pending
        if name in all_existing:
            continue

        suggestion = SkillSuggestion(
            id=str(uuid.uuid4()),
            user_id=user.id,
            suggested_name=name,
            suggested_description=pattern.get("suggested_description"),
            suggested_skill_type=pattern.get("suggested_skill_type", "instruction"),
            suggested_instructions=pattern.get("suggested_instructions"),
            pattern_summary=pattern.get("pattern_summary"),
            source_conversation_ids=pattern.get("source_conversation_ids"),
            confidence=confidence,
            status="pending",
        )
        db.add(suggestion)
        all_existing.append(name)
        created += 1

    if created > 0:
        db.commit()
        logger.info(f"Created {created} skill suggestion(s) for user {user.id}")
    else:
        logger.info(f"No new skill patterns found for user {user.id}")
