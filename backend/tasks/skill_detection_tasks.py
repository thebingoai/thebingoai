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

Previously dismissed patterns (do NOT suggest similar skills):
{dismissed_patterns}

Rules:
- Only return patterns with confidence >= 0.7
- Only suggest genuinely repeated patterns (seen 3+ times)
- Do not suggest skills that overlap existing skill names
- Do not suggest skills similar to previously dismissed patterns
- Return an empty array [] if no patterns qualify
- Return ONLY valid JSON, no other text"""


_EVALUATION_PROMPT = """Evaluate whether this suggested skill would genuinely save the user time.

Skill name: {name}
Skill description: {description}
Pattern summary: {pattern_summary}
User's message count in the last 14 days: {message_count}

Return a JSON object:
{{
  "recommendation": "recommended" | "low_value",
  "recommendation_reason": "1-2 sentence explanation addressed to the user, starting with 'I'd recommend this' or 'This seems low-value'",
  "frequency_count": <estimated number of times the pattern was observed>
}}

Guidelines:
- "recommended" = pattern is genuinely repeated (5+ times) and automatable
- "low_value" = pattern is infrequent, one-off, or not worth automating
- Be honest — most patterns are low-value
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


def _notify_new_suggestions(user_id: str, suggestions: list):
    """Push a skill_suggestions.new event to the user via WebSocket."""
    if not suggestions:
        return

    try:
        from backend.services.ws_connection_manager import ConnectionManager

        payload = {
            "type": "skill_suggestions.new",
            "suggestions": [
                {
                    "id": s.id,
                    "suggested_name": s.suggested_name,
                    "suggested_description": s.suggested_description,
                    "suggested_skill_type": s.suggested_skill_type,
                    "pattern_summary": s.pattern_summary,
                    "confidence": s.confidence,
                    "status": s.status,
                    "recommendation": s.recommendation,
                    "recommendation_reason": s.recommendation_reason,
                    "frequency_count": s.frequency_count,
                }
                for s in suggestions
            ],
        }
        ConnectionManager.publish_to_user_sync(user_id, payload)
        logger.info(f"Pushed {len(suggestions)} skill suggestion(s) via WS for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to push skill suggestions via WS for user {user_id}: {e}")


def _evaluate_suggestions(db, user, suggestions: list, message_count: int):
    """Run a second LLM pass to evaluate each suggestion's usefulness."""
    if not suggestions:
        return

    try:
        provider = get_provider(settings.default_llm_provider)
        import asyncio

        for suggestion in suggestions:
            try:
                prompt = _EVALUATION_PROMPT.format(
                    name=suggestion.suggested_name,
                    description=suggestion.suggested_description or "",
                    pattern_summary=suggestion.pattern_summary or "",
                    message_count=message_count,
                )

                async def _evaluate():
                    return await provider.chat(
                        [
                            {"role": "system", "content": "You are a skill evaluator. Return only valid JSON."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                    )

                response = asyncio.run(_evaluate())
                text = response.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1]) if len(lines) > 2 else text

                result = json.loads(text)
                suggestion.recommendation = result.get("recommendation")
                suggestion.recommendation_reason = result.get("recommendation_reason")
                suggestion.frequency_count = result.get("frequency_count")

            except (json.JSONDecodeError, ValueError, Exception) as e:
                logger.warning(
                    f"Evaluation failed for suggestion '{suggestion.suggested_name}': {e}"
                )

        db.commit()
    except Exception as e:
        logger.error(f"Evaluation pass failed for user {user.id}: {e}")


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

    # Load dismissed suggestions for exclusion
    dismissed = db.query(
        SkillSuggestion.suggested_name, SkillSuggestion.pattern_summary
    ).filter(
        SkillSuggestion.user_id == user.id,
        SkillSuggestion.status == "dismissed",
    ).all()

    all_existing = (
        existing_names
        + [s.suggested_name for s in pending_names]
        + [d.suggested_name for d in dismissed]
    )

    # Call LLM for pattern analysis
    try:
        provider = get_provider(settings.default_llm_provider)
        import asyncio

        # Format dismissed patterns for the prompt
        if dismissed:
            dismissed_text = "\n".join(
                f"- {d.suggested_name}: {d.pattern_summary or 'no summary'}"
                for d in dismissed
            )
        else:
            dismissed_text = "none"

        async def _analyze():
            prompt = _DETECTION_PROMPT.format(
                messages=messages_text,
                existing_skills=", ".join(all_existing) if all_existing else "none",
                dismissed_patterns=dismissed_text,
            )
            return await provider.chat(
                [
                    {"role": "system", "content": "You are a skill pattern analyzer. Return only valid JSON arrays."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )

        # --- Credit context setup (bingo-credits plugin) ---
        _credit_mgr = None
        try:
            from backend.plugins.loader import get_loaded_plugins
            if "bingo-credits" in get_loaded_plugins():
                from bingo_credits.credit_context import CreditContextManager
                _credit_mgr = CreditContextManager(
                    db=db,
                    user_id=user.id,
                    title=f"Skill detection: {user.id}",
                    provider_name=settings.default_llm_provider,
                    conversation_id=None,
                    block_on_insufficient=False,
                )
        except Exception as _credit_err:
            logger.warning("Credit context setup failed for skill detection: %s", _credit_err)
            _credit_mgr = None

        from contextlib import nullcontext
        with (_credit_mgr if _credit_mgr is not None else nullcontext()):
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

    created_suggestions = []
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
        created_suggestions.append(suggestion)
        all_existing.append(name)

    if created_suggestions:
        db.commit()
        logger.info(f"Created {len(created_suggestions)} skill suggestion(s) for user {user.id}")

        # Evaluate each new suggestion
        _evaluate_suggestions(db, user, created_suggestions, message_count)

        # Push via WebSocket
        _notify_new_suggestions(user.id, created_suggestions)
    else:
        logger.info(f"No new skill patterns found for user {user.id}")
