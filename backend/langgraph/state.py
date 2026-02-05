from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ContextSource(TypedDict):
    """Source information for a retrieved context chunk."""
    source: str
    chunk_index: int
    score: float


class ConversationState(TypedDict):
    """State for the RAG conversation graph."""

    # Conversation messages (with automatic history management)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Current question being processed
    question: str

    # Retrieved context chunks
    context: list[dict]

    # Namespace for vector search
    namespace: str

    # Selected LLM provider
    provider: str

    # Model override (optional)
    model: str | None

    # Whether context was found
    has_context: bool

    # Final answer (set by generate node)
    answer: str | None

    # Sources used in the answer
    sources: list[ContextSource]
