"""Shared title generation for chat conversations."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_TITLE_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "ollama": None,  # uses provider default
}


def fallback_title(user_message: str) -> str:
    """Derive a simple title from the user's first message. Never raises."""
    words = (user_message or "").strip().split()
    if not words:
        return "Untitled"
    snippet = " ".join(words[:6])[:60].rstrip(".,!?;:")
    return snippet.title() or "Untitled"


def _extract_step_context(steps: list) -> str:
    """Build a context hint from agent steps (tools used, first SQL snippet)."""
    if not steps:
        return ""

    tool_names = []
    first_sql = None

    for step in steps:
        name = step.get("tool_name")
        if name and name not in tool_names:
            tool_names.append(name)
        if first_sql is None and name == "execute_query":
            sql = (
                step.get("content", {}).get("args", {}).get("sql")
                or step.get("content", {}).get("result", {}).get("sql")
            )
            if sql:
                first_sql = sql[:120].replace("\n", " ").strip()

    lines = []
    if tool_names:
        lines.append(f"Tools used: {', '.join(tool_names)}")
    if first_sql:
        lines.append(f"SQL: {first_sql}")

    return "\n".join(lines)


async def generate_title(
    user_message: str,
    assistant_response: str,
    steps: Optional[list] = None,
) -> str:
    """Generate a specific, descriptive title for a new conversation."""
    from backend.llm.factory import get_provider
    from backend.config import settings

    provider_name = settings.default_llm_provider or "openai"
    model = _TITLE_MODELS.get(provider_name)
    provider = get_provider(provider_name, model=model)

    context_block = _extract_step_context(steps or [])
    context_section = f"\nContext:\n{context_block}" if context_block else ""

    prompt = (
        f"You are naming a data analytics chat session.\n\n"
        f"User asked: {user_message}\n"
        f"Assistant replied: {assistant_response[:400]}"
        f"{context_section}\n\n"
        "Write a short title (4-7 words) that names the specific business question or metric explored. "
        "Avoid generic words like 'analysis', 'query', 'data', or 'conversation'. "
        "Capitalise each word. Return ONLY the title text."
    )

    messages = [{"role": "user", "content": prompt}]
    raw = await provider.chat(messages, temperature=0.3, max_tokens=30)
    title = raw.strip().strip('"\'').rstrip(".,!?;:")[:80]
    return title or "Untitled"
