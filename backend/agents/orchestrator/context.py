"""Agent context for request-scoped data."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentContext:
    """
    Request-scoped context for agent execution.

    Replaces global state pattern with explicit context passing via closures.
    Each request creates a new AgentContext instance.

    Attributes:
        user_id: Unique user identifier for authorization
        thread_id: Conversation thread ID for memory/checkpointing
        available_connections: Database connection IDs user can access
        memory_context: Pre-fetched memory context (passive injection)
        provider: LLM provider name ("openai", "anthropic", "ollama")
        model: Optional model override (uses provider default if None)
        temperature: LLM sampling temperature (0.0-1.0)
    """

    user_id: str
    thread_id: str
    available_connections: List[int] = field(default_factory=list)
    memory_context: str = ""
    provider: str = "openai"
    model: Optional[str] = None
    temperature: float = 0.7
