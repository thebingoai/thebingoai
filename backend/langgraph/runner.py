"""LangGraph RAG workflow runner."""

import uuid
from typing import Optional, AsyncGenerator, Union

from backend.langgraph.nodes import create_rag_graph
from backend.langgraph.state import ConversationState
from backend.services.job_store import redis_client
import logging

logger = logging.getLogger(__name__)

# In-memory conversation store (use Redis in production)
CONVERSATION_PREFIX = "conv:"
CONVERSATION_TTL = 86400 * 7  # 7 days


def _get_thread_key(thread_id: str) -> str:
    """Get Redis key for conversation thread."""
    return f"{CONVERSATION_PREFIX}{thread_id}"


def _create_thread_id() -> str:
    """Generate a new thread ID."""
    return str(uuid.uuid4())


async def run_rag_query(
    question: str,
    namespace: str = "default",
    provider: str = "openai",
    model: Optional[str] = None,
    thread_id: Optional[str] = None,
    stream: bool = False
) -> Union[dict, AsyncGenerator[dict, None]]:
    """
    Run a RAG query through the LangGraph workflow.

    Args:
        question: User's question
        namespace: Pinecone namespace to search
        provider: LLM provider name
        model: Optional model override
        thread_id: Optional conversation thread ID
        stream: Whether to stream response

    Returns:
        If stream=False: dict with answer, sources, thread_id
        If stream=True: AsyncGenerator yielding stream events
    """
    # Create or use existing thread
    if thread_id is None:
        thread_id = _create_thread_id()
        logger.info(f"Created new thread: {thread_id}")
    else:
        logger.info(f"Using existing thread: {thread_id}")

    if stream:
        return _run_streaming(question, namespace, provider, model, thread_id)
    else:
        return await _run_sync(question, namespace, provider, model, thread_id)


async def _run_sync(
    question: str,
    namespace: str,
    provider: str,
    model: Optional[str],
    thread_id: str
) -> dict:
    """Run RAG query synchronously (non-streaming)."""
    # Create the graph
    graph = create_rag_graph()

    # Initial state
    initial_state: ConversationState = {
        "question": question,
        "namespace": namespace,
        "provider": provider,
        "model": model,
        "context": [],
        "sources": [],
        "answer": "",
        "messages": [],
        "has_context": False,
        "thread_id": thread_id
    }

    # Config for checkpointing
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Run the graph
        result = await graph.ainvoke(initial_state, config=config)

        return {
            "answer": result.get("answer", ""),
            "sources": [
                {
                    "source": s["source"],
                    "chunk_index": s["chunk_index"],
                    "score": s["score"]
                }
                for s in result.get("sources", [])
            ],
            "thread_id": thread_id,
            "has_context": result.get("has_context", False)
        }

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise


async def _run_streaming(
    question: str,
    namespace: str,
    provider: str,
    model: Optional[str],
    thread_id: str
) -> AsyncGenerator[dict, None]:
    """Run RAG query with streaming response."""
    graph = create_rag_graph()

    initial_state: ConversationState = {
        "question": question,
        "namespace": namespace,
        "provider": provider,
        "model": model,
        "context": [],
        "sources": [],
        "answer": "",
        "messages": [],
        "has_context": False,
        "thread_id": thread_id
    }

    config = {"configurable": {"thread_id": thread_id}}

    # First yield the sources (context retrieval)
    # We'll need to handle this differently - LangGraph doesn't natively stream node outputs
    # So we'll run the retrieve step first, then stream the generation

    try:
        # Run to get context first
        result = await graph.ainvoke(initial_state, config=config)

        # Yield sources
        yield {
            "type": "sources",
            "sources": [
                {
                    "source": s.source,
                    "chunk_index": s.chunk_index,
                    "score": s.score
                }
                for s in result.get("sources", [])
            ]
        }

        # Yield thread ID
        yield {
            "type": "thread_id",
            "thread_id": thread_id
        }

        # Now we need to get the LLM and stream from it directly
        # This is a simplified approach - for production, you'd want proper LangGraph streaming
        from backend.llm.factory import get_provider

        llm = get_provider(provider, model)

        # Build messages from the graph result
        # The graph has already processed the context and created messages
        messages = result.get("messages", [])

        # Convert LangChain messages to dict format
        message_dicts = []
        for msg in messages:
            if hasattr(msg, 'type') and hasattr(msg, 'content'):
                role = 'assistant' if msg.type == 'ai' else 'user'
                message_dicts.append({"role": role, "content": msg.content})

        # If no messages were created, we need to construct them
        if not message_dicts:
            # This shouldn't happen if the graph ran correctly
            logger.warning("No messages in graph result, constructing fallback")
            # We need to reconstruct the conversation - this is a fallback
            message_dicts = [{"role": "user", "content": question}]

        # Stream the response
        full_content = ""
        async for chunk in llm.chat_stream(message_dicts, temperature=0.7):
            full_content += chunk
            yield {
                "type": "token",
                "token": chunk
            }

        # Yield completion
        yield {
            "type": "done",
            "thread_id": thread_id
        }

    except Exception as e:
        logger.error(f"Streaming RAG query failed: {e}")
        yield {
            "type": "error",
            "error": str(e)
        }


async def get_conversation_history(thread_id: str) -> list[dict]:
    """
    Get conversation history for a thread.

    Args:
        thread_id: Thread ID

    Returns:
        List of message dicts with role and content
    """
    try:
        # Try to get from LangGraph's memory saver
        # This is a simplified implementation
        # In production, you'd want to properly serialize/deserialize

        # For now, return empty - proper implementation would query the checkpoint
        logger.info(f"Getting history for thread {thread_id}")

        # The conversation is stored in LangGraph's MemorySaver
        # We could access it via the graph's checkpointer but that's complex
        # For now, we'll return an empty list and document this limitation
        return []

    except Exception as e:
        logger.error(f"Failed to get conversation history: {e}")
        return []


async def clear_conversation(thread_id: str) -> bool:
    """
    Clear conversation history for a thread.

    Args:
        thread_id: Thread ID

    Returns:
        True if cleared, False if not found
    """
    try:
        # Clear from Redis if stored there
        key = _get_thread_key(thread_id)
        result = redis_client.delete(key)

        logger.info(f"Cleared conversation {thread_id}")
        return result > 0

    except Exception as e:
        logger.error(f"Failed to clear conversation: {e}")
        return False
