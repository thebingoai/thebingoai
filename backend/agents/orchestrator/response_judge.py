"""Layer-4 response-quality judge.

After the orchestrator produces a final answer, this judge evaluates whether
the answer actually resolves the user's question. If not, the orchestrator
retries once with the judge's directive.

Falls open on any error (judge timeout, provider failure, missing model config)
so chat never blocks on the judge itself.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pydantic import BaseModel, Field

from backend.config import settings
from backend.llm.factory import get_provider
from backend.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class JudgeVerdict(BaseModel):
    """Structured verdict returned by the judge LLM."""

    resolved: bool = Field(
        description="True if the response fully answers the user's question; false if it dodged, offered a retry, leaked a technical error, or left the task incomplete.",
    )
    reason: str = Field(
        description="One short sentence explaining the verdict — used for logs and failure-case capture.",
    )
    suggested_directive: str = Field(
        default="",
        description="If resolved=false, a direct instruction to the assistant on how to finish the task (reference the fix it already proposed, tell it not to ask). Empty when resolved=true.",
    )


_JUDGE_SYSTEM_PROMPT = """You evaluate whether an assistant's response fully resolves a user's question.

Mark `resolved: false` when ANY of these are true:
- The response offers to retry with a fix but asks the user for permission ("if you want, I can...", "shall I...", "would you like me to...")
- The response acknowledges it couldn't complete the task ("I couldn't fully compute", "I was unable to...", "the tool failed")
- The response leaks a technical error message (exception types, stack traces, serialization errors like Decimal/JSON, SQL error codes)
- The response gives partial data where a full answer was asked for, without the user having limited scope

Mark `resolved: true` when:
- The response directly answers what the user asked
- The response asks a SEMANTIC clarification the user must answer (e.g., "which of these two tables?", "include canceled orders?") — that's a legitimate question, not a failure
- The response explains a terminal limitation in plain language and offers a real next step (NOT a retry-with-fix offer)

When `resolved: false`, write `suggested_directive` as a direct instruction to the assistant on how to complete the task. Reference the fix the assistant already proposed (if present), and tell it to proceed without asking for permission."""


async def judge_response(
    user_question: str,
    response: str,
    llm_provider: Optional[BaseLLMProvider] = None,
) -> JudgeVerdict:
    """Evaluate whether `response` resolves `user_question`.

    Returns a `JudgeVerdict`. Always returns — falls open (resolved=True) on
    any exception, timeout, or missing config so the judge never blocks chat.

    Args:
        user_question: The user's original question for this turn.
        response: The orchestrator's final answer (already redacted/sanitized).
        llm_provider: Optional override; normally the judge resolves its own
            provider from settings.judge_llm_provider.
    """
    if not settings.judge_enabled:
        return JudgeVerdict(resolved=True, reason="judge disabled")
    if not settings.judge_llm_model:
        logger.warning(
            "JUDGE_LLM_MODEL not configured in .env — Layer-4 judge disabled, falling open"
        )
        return JudgeVerdict(resolved=True, reason="judge model not configured")
    if not response or not response.strip():
        return JudgeVerdict(resolved=True, reason="empty response, nothing to judge")

    provider_name = settings.judge_llm_provider or settings.default_llm_provider
    try:
        provider = llm_provider or get_provider(provider_name)
        llm = provider.get_langchain_llm(model=settings.judge_llm_model)
        structured_llm = llm.with_structured_output(JudgeVerdict)

        verdict: JudgeVerdict = await asyncio.wait_for(
            structured_llm.ainvoke(
                [
                    {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"USER QUESTION:\n{user_question}\n\nASSISTANT RESPONSE:\n{response}",
                    },
                ]
            ),
            timeout=settings.judge_timeout_seconds,
        )
        return verdict
    except asyncio.TimeoutError:
        logger.warning(
            "Response judge timed out after %ds — falling open", settings.judge_timeout_seconds
        )
        return JudgeVerdict(resolved=True, reason="judge timeout")
    except Exception as exc:
        logger.warning("Response judge failed, falling open: %s", exc)
        return JudgeVerdict(resolved=True, reason=f"judge error: {type(exc).__name__}")
