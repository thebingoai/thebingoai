"""Memory generator for daily summaries."""

from sqlalchemy.orm import Session
from backend.services.conversation_service import ConversationService
from backend.services.token_tracking_service import TokenTrackingService
from backend.models.token_usage import OperationType
from backend.llm.factory import get_llm_provider
from backend.config import settings
from backend.memory.storage import MemoryStorage
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timedelta
from typing import Dict, Any
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

MEMORY_GENERATION_PROMPT = """You are a memory system that summarizes user interactions with a Business Intelligence agent.

Given the user's conversations from the past day, generate a concise summary that captures:
1. Common questions or topics the user asked about
2. Database tables/schemas the user frequently queries
3. Any patterns in the user's query style or preferences
4. Errors or corrections that occurred
5. Key insights or learnings

Conversations:
{conversations}

Generate a JSON summary with the following structure:
{{
  "summary": "Natural language summary of the day's interactions",
  "common_questions": ["Question 1", "Question 2", ...],
  "common_tables": ["table1", "table2", ...],
  "query_patterns": ["pattern1", "pattern2", ...],
  "corrections": ["correction1", "correction2", ...],
  "insights": ["insight1", "insight2", ...]
}}

Return ONLY the JSON, no additional text."""


class MemoryGenerator:
    """Generate daily memory summaries for users."""

    def __init__(self):
        self.storage = MemoryStorage()
        self.llm = get_llm_provider(settings.default_llm_provider)

    async def generate_daily_memory(self, db: Session, user_id: str, date: datetime) -> Dict[str, Any]:
        """
        Generate a daily memory summary for a user.

        Args:
            db: Database session
            user_id: User ID
            date: Date to generate memory for

        Returns:
            Memory summary dictionary
        """
        # Get all conversations from the day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        conversations = ConversationService.list_conversations(db, user_id, limit=100)

        # Filter to conversations from the target date
        daily_conversations = [
            conv for conv in conversations
            if start_of_day <= conv.created_at < end_of_day
        ]

        if not daily_conversations:
            return {
                "summary": "No interactions on this day",
                "common_questions": [],
                "common_tables": [],
                "query_patterns": [],
                "corrections": [],
                "insights": []
            }

        # Build conversation text
        conversation_texts = []
        for conv in daily_conversations:
            messages = ConversationService.get_conversation_history(
                db, conv.thread_id, user_id
            )
            conv_text = f"Conversation (ID: {conv.thread_id}):\n"
            for msg in messages:
                conv_text += f"  {msg.role}: {msg.content}\n"
            conversation_texts.append(conv_text)

        all_conversations = "\n\n".join(conversation_texts)

        # Generate summary using LLM
        prompt = MEMORY_GENERATION_PROMPT.format(conversations=all_conversations)
        messages = [
            HumanMessage(content=prompt)
        ]

        response = self.llm.chat(messages)

        # Track token usage (rough estimation)
        # TODO: Get actual token counts from LLM provider response
        prompt_tokens = int(len(prompt.split()) * 1.3)
        completion_tokens = int(len(response.split()) * 1.3)

        TokenTrackingService.track_usage(
            db=db,
            user_id=user_id,
            operation=OperationType.MEMORY_GENERATION,
            model=settings.default_llm_model or "gpt-4o",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )

        # Parse JSON response
        try:
            summary = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            logger.warning(f"Failed to parse LLM response as JSON for user {user_id}")
            summary = {
                "summary": response[:500],  # First 500 chars
                "common_questions": [],
                "common_tables": [],
                "query_patterns": [],
                "corrections": [],
                "insights": []
            }

        # Store in Qdrant
        memory_text = summary["summary"]
        metadata = {
            "query_count": len(daily_conversations),
            "common_tables": json.dumps(summary.get("common_tables", [])),
            "query_patterns": json.dumps(summary.get("query_patterns", []))
        }

        memory_id = await self.storage.store_memory(
            user_id=user_id,
            memory_text=memory_text,
            date=date,
            metadata=metadata
        )

        summary["memory_id"] = memory_id
        summary["date"] = date.isoformat()

        logger.info(f"Generated memory {memory_id} for user {user_id}")
        return summary
