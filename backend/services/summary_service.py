import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.conversation_summary import ConversationSummary
from backend.config import settings

logger = logging.getLogger(__name__)

MODEL_CONTEXT_WINDOWS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "claude-sonnet-4-20250514": 200000,
    "claude-opus-4-20250514": 200000,
    "claude-haiku-3-5-20241022": 200000,
}

_SUMMARY_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-3-5-20241022",
    "ollama": None,
}


class SummaryService:
    @staticmethod
    async def generate_or_update_summary(db: Session, conversation_id: int, user_message: str, assistant_response: str) -> ConversationSummary:
        from backend.llm.factory import get_provider

        existing = db.query(ConversationSummary).filter_by(conversation_id=conversation_id).first()

        existing_text = existing.summary_text if existing else ""

        prompt_parts = []
        if existing_text:
            prompt_parts.append(f"Current summary: {existing_text}")
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append(f"Assistant: {assistant_response[:500]}")
        prompt_parts.append("Write an updated 1-3 sentence summary of what this conversation is about. Return ONLY the summary text.")

        provider_name = settings.default_llm_provider or "openai"
        model = _SUMMARY_MODELS.get(provider_name)
        provider = get_provider(provider_name, model=model)

        messages = [{"role": "user", "content": "\n\n".join(prompt_parts)}]
        raw = await provider.chat(messages, temperature=0.3, max_tokens=150)
        summary_text = raw.strip()[:500]

        if not summary_text:
            summary_text = existing_text or "Conversation in progress."

        if existing:
            existing.summary_text = summary_text
            existing.updated_at = datetime.utcnow()
        else:
            existing = ConversationSummary(
                conversation_id=conversation_id,
                summary_text=summary_text,
            )
            db.add(existing)

        db.commit()
        db.refresh(existing)
        return existing

    @staticmethod
    async def generate_full_summary(db: Session, conversation_id: int) -> ConversationSummary:
        """Generate a summary from the full conversation history (for manual trigger)."""
        from backend.llm.factory import get_provider
        from backend.models.message import Message

        messages = db.query(Message).filter_by(conversation_id=conversation_id).order_by(Message.id).all()
        if not messages:
            raise ValueError("No messages in conversation")

        # Build condensed transcript, truncated to ~2000 chars
        transcript_parts = []
        total_len = 0
        for m in messages:
            role = "User" if m.role == "user" else "Assistant"
            text = (m.content or "")[:300]
            line = f"{role}: {text}"
            if total_len + len(line) > 2000:
                transcript_parts.append("... (earlier messages truncated)")
                break
            transcript_parts.append(line)
            total_len += len(line)

        prompt = "\n\n".join(transcript_parts) + "\n\nWrite a 1-3 sentence summary of what this conversation is about. Return ONLY the summary text."

        provider_name = settings.default_llm_provider or "openai"
        model = _SUMMARY_MODELS.get(provider_name)
        provider = get_provider(provider_name, model=model)

        llm_messages = [{"role": "user", "content": prompt}]
        raw = await provider.chat(llm_messages, temperature=0.3, max_tokens=150)
        summary_text = raw.strip()[:500] or "Conversation in progress."

        existing = db.query(ConversationSummary).filter_by(conversation_id=conversation_id).first()
        if existing:
            existing.summary_text = summary_text
            existing.updated_at = datetime.utcnow()
        else:
            existing = ConversationSummary(
                conversation_id=conversation_id,
                summary_text=summary_text,
            )
            db.add(existing)

        db.commit()
        db.refresh(existing)
        return existing

    @staticmethod
    def get_summary(db: Session, conversation_id: int):
        return db.query(ConversationSummary).filter_by(conversation_id=conversation_id).first()

    @staticmethod
    def estimate_conversation_tokens(db: Session, conversation_id: int) -> int:
        from backend.models.message import Message
        messages = db.query(Message).filter_by(conversation_id=conversation_id).all()
        total_words = sum(len((m.content or "").split()) for m in messages)
        return int(total_words * 1.3)

    @staticmethod
    def get_token_limit() -> int:
        model = settings.default_llm_model or settings.openai_default_model or "gpt-4o"
        return MODEL_CONTEXT_WINDOWS.get(model, 128000)
