from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
from backend.models.requests import AskRequest
from backend.models.responses import AskResponse, SourceInfo, ProviderInfo, ProvidersResponse
from backend.langgraph.runner import run_rag_query, get_conversation_history, clear_conversation
from backend.config import settings
import json
import httpx
import logging

logger = logging.getLogger(__name__)


async def ask(request: AskRequest) -> StreamingResponse | AskResponse:
    """
    Ask a question with RAG using LangGraph workflow.

    Supports conversation memory via thread_id and streaming responses.

    Args:
        request: Ask request with question, namespace, provider, etc.

    Returns:
        StreamingResponse if request.stream is True
        AskResponse with answer and sources otherwise
    """
    if request.stream:
        return StreamingResponse(
            stream_response(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    result = await run_rag_query(
        question=request.question,
        namespace=request.namespace,
        provider=request.provider,
        model=request.model,
        thread_id=request.thread_id,
        stream=False
    )

    return AskResponse(
        answer=result["answer"],
        sources=[SourceInfo(**s) for s in result["sources"]],
        provider=request.provider,
        model=request.model or "default",
        thread_id=result["thread_id"],
        has_context=result["has_context"]
    )


async def stream_response(request: AskRequest) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream using LangGraph.

    Args:
        request: Ask request with streaming enabled

    Yields:
        Server-sent events (SSE) formatted strings
    """
    try:
        stream = await run_rag_query(
            question=request.question,
            namespace=request.namespace,
            provider=request.provider,
            model=request.model,
            thread_id=request.thread_id,
            stream=True
        )

        async for event in stream:
            if event["type"] == "sources":
                yield f"data: {json.dumps({'sources': event['sources']})}\n\n"
            elif event["type"] == "token":
                yield f"data: {json.dumps({'token': event['token']})}\n\n"
            elif event["type"] == "done":
                yield f"data: {json.dumps({'thread_id': event['thread_id']})}\n\n"
                yield "data: [DONE]\n\n"
            elif event["type"] == "error":
                yield f"data: {json.dumps({'error': event['error']})}\n\n"
                yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error in stream_response: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


async def list_providers() -> ProvidersResponse:
    """
    List available LLM providers and their status.

    Returns:
        ProvidersResponse with available providers, models, and defaults
    """
    providers = []

    # OpenAI - always available if API key is set
    providers.append(ProviderInfo(
        name="openai",
        available=bool(settings.openai_api_key),
        models=["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
    ))

    # Anthropic
    providers.append(ProviderInfo(
        name="anthropic",
        available=bool(settings.anthropic_api_key),
        models=["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
    ))

    # Ollama - check if running
    ollama_available = False
    ollama_models = []
    ollama_error = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                ollama_available = True
                data = response.json()
                ollama_models = [m["name"] for m in data.get("models", [])][:5]
    except Exception as e:
        ollama_error = str(e)

    providers.append(ProviderInfo(
        name="ollama",
        available=ollama_available,
        models=ollama_models or ["llama3", "mistral", "codellama"],
        error=ollama_error
    ))

    return ProvidersResponse(
        providers=providers,
        default={
            "provider": settings.default_llm_provider,
            "model": settings.default_llm_model or "default"
        }
    )


async def get_history(thread_id: str) -> dict:
    """
    Get conversation history for a thread.

    Args:
        thread_id: Conversation thread identifier

    Returns:
        Dict with thread_id and messages list
    """
    history = await get_conversation_history(thread_id)
    return {"thread_id": thread_id, "messages": history}


async def delete_history(thread_id: str) -> dict:
    """
    Clear conversation history for a thread.

    Args:
        thread_id: Conversation thread identifier

    Returns:
        Dict with status and thread_id

    Raises:
        HTTPException: 404 if thread not found
    """
    success = await clear_conversation(thread_id)
    if success:
        return {"status": "cleared", "thread_id": thread_id}
    raise HTTPException(404, "Thread not found")
