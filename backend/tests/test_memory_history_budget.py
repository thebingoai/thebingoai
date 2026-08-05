"""memory_history_max_messages is a budget for the whole memory prompt.

It used to be spent per conversation, so a busy day could assemble
list_conversations' 100 threads (plus the permanent one) x the full allowance —
~50,500 messages — into a single LLM call.

No pytest-asyncio in this repo; the coroutine is driven with asyncio.run.
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.config import settings

DAY = datetime(2026, 1, 1, 12, 0, 0)
USER_ID = "user-1"


def _conv(i):
    return SimpleNamespace(
        thread_id=f"t-{i}",
        created_at=DAY,
        id=i,
    )


def _messages(n, thread_id):
    return [
        SimpleNamespace(role="user", content=f"{thread_id}-m{j}")
        for j in range(n)
    ]


@pytest.fixture
def generator():
    """MemoryGenerator with its two constructor side effects stubbed out."""
    from backend.memory import generator as gen_mod

    storage = MagicMock()
    storage.store_memory = AsyncMock(return_value="mem-1")  # awaited by the generator

    with patch.object(gen_mod, "MemoryStorage", return_value=storage), \
         patch.object(gen_mod, "get_provider"):
        yield gen_mod.MemoryGenerator()


def _run(generator, conversations, per_conversation_messages):
    """Drive generate_daily_memory, recording the `limit` each history call got.

    Returns (limits_requested, total_messages_pulled).
    """
    from backend.memory import generator as gen_mod

    limits: list[int] = []

    def _fake_history(db, thread_id, user_id, limit=None, since_reset=True):
        limits.append(limit)
        # Honour the limit the way the real SQL window does.
        return _messages(min(per_conversation_messages, limit), thread_id)

    async def _fake_chat(messages):
        return '{"summary": "s", "common_questions": [], "common_tables": [], ' \
               '"query_patterns": [], "corrections": [], "insights": []}'

    generator.llm.chat = _fake_chat

    with patch.object(gen_mod.ConversationService, "list_conversations",
                      return_value=(conversations, False)), \
         patch.object(gen_mod.ConversationService, "get_or_create_permanent_conversation",
                      return_value=None), \
         patch.object(gen_mod.ConversationService, "get_conversation_history",
                      side_effect=_fake_history), \
         patch.object(gen_mod.TokenTrackingService, "track_usage"):
        asyncio.run(generator.generate_daily_memory(object(), USER_ID, DAY))

    return limits, sum(min(per_conversation_messages, lim) for lim in limits)


def test_budget_is_global_not_per_conversation(generator):
    budget = settings.memory_history_max_messages
    conversations = [_conv(i) for i in range(101)]

    limits, total = _run(generator, conversations, per_conversation_messages=budget)

    assert total <= budget, (
        f"pulled {total} messages against a {budget} budget — the allowance is "
        "resetting per conversation"
    )


def test_budget_shrinks_as_it_is_spent(generator):
    budget = settings.memory_history_max_messages
    conversations = [_conv(i) for i in range(10)]

    limits, total = _run(generator, conversations, per_conversation_messages=10)

    assert limits[0] == budget
    assert limits[1] == budget - 10
    assert limits[2] == budget - 20
    assert total == 100


def test_loop_stops_once_the_budget_is_gone(generator):
    budget = settings.memory_history_max_messages
    conversations = [_conv(i) for i in range(50)]

    # Each conversation eats the whole budget → only the first is ever read.
    limits, _ = _run(generator, conversations, per_conversation_messages=budget)

    assert len(limits) == 1, "later conversations must not be queried at all"


def test_a_light_day_is_unaffected(generator):
    conversations = [_conv(i) for i in range(3)]

    limits, total = _run(generator, conversations, per_conversation_messages=5)

    assert len(limits) == 3, "every conversation still read when under budget"
    assert total == 15
