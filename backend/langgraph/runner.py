"""LangGraph RAG workflow runner with improved streaming support."""

import uuid
from typing import Optional, AsyncGenerator, Union

from backend.langgraph.nodes import create_rag_graph
from backend.langgraph.state import ConversationState
from backend.llm.factory import get_provider
from backend.prompts import SYSTEM_PROMPT, NO_CONTEXT_PROMPT
import logging

logger = logging.getLogger(__name__)

# Conversation storage constants
CONVERSATION_PREFIX = "conv:"
CONVERSATION_TTL = 86400 * 7  # 7 days


def _get_thread_key(thread_id: str) -> str:
    """
    Get Redis key for conversation thread.

    Args:
        thread_id: Thread identifier

    Returns:
        Redis key string
    """
    return f"{CONVERSATION_PREFIX}{thread_id}"


def _create_thread_id() -> str:
    """
    Generate a new unique thread ID.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def _build_initial_state(
    question: str,
    namespace: str,
    provider: str,
    model: Optional[str],
    thread_id: str
) -> ConversationState:
    """
    Build the initial state for the RAG graph.

    Args:
        question: User's question
        namespace: Vector namespace to search
        provider: LLM provider name
        model: Optional model override
        thread_id: Conversation thread ID

    Returns:
        Initial ConversationState dict
    """
    return {
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


def _format_sources(sources: list) -> list[dict]:
    """
    Format sources for API response.

    Args:
        sources: List of source objects (dict or ContextSource)

    Returns:
        List of formatted source dicts
    """
    formatted = []
    for s in sources:
        if hasattr(s, 'source'):  # ContextSource object
            formatted.append({
                "source": s.source,
                "chunk_index": s.chunk_index,
                "score": s.score
            })
        else:  # dict
            formatted.append({
                "source": s.get("source"),
                "chunk_index": s.get("chunk_index"),
                "score": s.get("score")
            })
    return formatted


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
    """
    Run RAG query synchronously (non-streaming).

    Args:
        question: User's question
        namespace: Vector namespace to search
        provider: LLM provider name
        model: Optional model override
        thread_id: Conversation thread ID

    Returns:
        Dict with answer, sources, thread_id, has_context
    """
    logger.debug(f"Running sync RAG query for thread {thread_id}")
    graph = create_rag_graph()

    initial_state = _build_initial_state(
        question, namespace, provider, model, thread_id
    )

    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = await graph.ainvoke(initial_state, config=config)

        return {
            "answer": result.get("answer", ""),
            "sources": _format_sources(result.get("sources", [])),
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
    """
    Run RAG query with streaming response.

    Yields events for sources, tokens, and completion.

    Args:
        question: User's question
        namespace: Vector namespace to search
        provider: LLM provider name
        model: Optional model override
        thread_id: Conversation thread ID

    Yields:
        Dicts with 'type' key ('sources', 'thread_id', 'token', 'done', 'error')
    """
    logger.debug(f"Running streaming RAG query for thread {thread_id}")
    graph = create_rag_graph()

    initial_state = _build_initial_state(
        question, namespace, provider, model, thread_id
    )

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Run graph to retrieve context and generate messages
        result = await graph.ainvoke(initial_state, config=config)

        # Yield sources first
        yield {
            "type": "sources",
            "sources": _format_sources(result.get("sources", []))
        }

        # Yield thread ID
        yield {
            "type": "thread_id",
            "thread_id": thread_id
        }

        # Build messages for streaming
        messages = _extract_messages(result, question)

        # Stream from LLM
        llm = get_provider(provider, model)
        async for token in llm.chat_stream(messages, temperature=0.7):
            yield {
                "type": "token",
                "token": token
            }

        # Signal completion
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


def _extract_messages(result: dict, question: str) -> list[dict]:
    """
    Extract and format messages from graph result for LLM.

    Args:
        result: Graph execution result
        question: Original user question

    Returns:
        List of message dicts with 'role' and 'content'
    """
    from langchain_core.messages import HumanMessage, AIMessage

    messages = result.get("messages", [])

    # Convert LangChain messages to dict format
    message_dicts = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            message_dicts.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            message_dicts.append({"role": "assistant", "content": msg.content})
        elif hasattr(msg, 'type') and hasattr(msg, 'content'):
            role = 'assistant' if msg.type == 'ai' else 'user'
            message_dicts.append({"role": role, "content": msg.content})

    # If no messages were created, construct from scratch
    if not message_dicts:
        logger.warning("No messages in graph result, constructing fallback")

        # Build context string from result
        context = result.get("context", [])
        if context:
            context_str = "\n\n---\n\n".join([
                f"[Source: {c['source']}, Section {c['chunk_index']}]\n{c['text']}"
                for c in context
            ])
            system_content = SYSTEM_PROMPT.format(context=context_str)
        else:
            system_content = NO_CONTEXT_PROMPT

        message_dicts = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question}
        ]

    return message_dicts


async def get_conversation_history(thread_id: str) -> list[dict]:
    """
    Get conversation history for a thread.

    Args:
        thread_id: Thread ID

    Returns:
        List of message dicts with role and content

    Note:
        This is a simplified implementation. Full implementation would
        query LangGraph's checkpoint for complete history.
    """
    logger.info(f"Getting history for thread {thread_id}")

    # The conversation is stored in LangGraph's MemorySaver
    # Full implementation would access graph state via checkpointer
    # For now, return empty list as documented limitation
    return []


async def clear_conversation(thread_id: str) -> bool:
    """
    Clear conversation history for a thread.

    Args:
        thread_id: Thread ID

    Returns:
        True if cleared, False if not found

    Note:
        This is a simplified implementation. Full implementation would
        clear the checkpoint from the checkpointer.
    """
    try:
        from backend.services.job_store import redis_client

        key = _get_thread_key(thread_id)
        result = redis_client.delete(key)

        logger.info(f"Cleared conversation {thread_id}")
        return result > 0

    except Exception as e:
        logger.error(f"Failed to clear conversation: {e}")
        return False
