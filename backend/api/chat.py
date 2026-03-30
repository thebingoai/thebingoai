from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.chat import ChatRequest, ChatResponse, ConversationResponse, ConversationListResponse, ConversationListSummaryResponse, MessageStepsResponse, UpdateTitleRequest, ArchiveRequest, ConversationSummaryResponse
from backend.services.conversation_service import ConversationService
from backend.services.token_tracking_service import TokenTrackingService
from backend.models.token_usage import OperationType
from backend.config import settings
from backend.llm.factory import get_provider
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


_TITLE_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


async def _generate_title(user_message: str, assistant_response: str) -> str:
    """Generate a concise title using a lightweight LLM call."""
    from backend.llm.factory import get_provider
    provider_name = settings.default_llm_provider or "openai"
    model = _TITLE_MODELS.get(provider_name)
    provider = get_provider(provider_name, model=model)

    messages = [
        {
            "role": "user",
            "content": (
                f"User: {user_message}\n\n"
                f"Assistant: {assistant_response[:500]}\n\n"
                "Generate a concise title (3-8 words) for this conversation. "
                "Return ONLY the title text."
            )
        }
    ]
    raw = await provider.chat(messages, temperature=0.3, max_tokens=30)
    title = raw.strip().strip('"\'').rstrip('.,!?;:')[:80]
    return title or "Untitled"


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process a chat message through the orchestrator agent.

    The orchestrator routes to specialized sub-agents based on intent:
    - Data Agent: For SQL database queries
    - RAG Agent: For document-based questions
    - Skills: For specialized tasks (summarization, etc.)
    """
    from backend.agents import run_orchestrator
    from backend.services.heartbeat_context import build_orchestrator_context

    # Get or create conversation
    if request.thread_id:
        conversation = ConversationService.get_conversation_by_thread(
            db, request.thread_id, current_user.id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = ConversationService.create_conversation(
            db, current_user.id, title="Untitled"
        )

    # Save user message
    ConversationService.add_message(db, conversation.id, "user", request.message)

    # Validate requested connection access
    if request.connection_ids:
        accessible = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.id.in_(request.connection_ids),
            DatabaseConnection.user_id == current_user.id
        ).all()
        if len(accessible) != len(request.connection_ids):
            raise HTTPException(status_code=403, detail="Access denied to one or more connections")

    # Build orchestrator context (connections, teams, skills, memories)
    ctx = await build_orchestrator_context(
        db=db,
        user=current_user,
        query=request.message,
        connection_ids=request.connection_ids or None,
        thread_id=conversation.thread_id,
    )

    # Fetch conversation history (exclude the just-saved user message)
    history = ConversationService.get_conversation_history(db, conversation.thread_id, current_user.id)
    history = history[:-1]
    # Truncate at last context reset boundary
    for i in range(len(history) - 1, -1, -1):
        if history[i].source == "context_reset":
            history = history[i + 1:]
            break

    # Resolve user's preferred LLM provider
    user_provider = get_provider(settings.default_llm_provider)

    # Run orchestrator
    from backend.database.session import SessionLocal
    result = await run_orchestrator(
        user_question=request.message,
        context=ctx.agent_context,
        history=history,
        custom_agents=ctx.custom_agents or None,
        db_session_factory=SessionLocal,
        memory_context=ctx.memory_context,
        user_skills=ctx.user_skills or None,
        user_memories_context=ctx.user_memories_context,
        skill_suggestions=ctx.skill_suggestions or None,
        soul_prompt=ctx.soul_prompt,
        profile=ctx.profile,
        llm_provider=user_provider,
    )

    # Save assistant message
    assistant_msg = ConversationService.add_message(
        db, conversation.id, "assistant", result["message"]
    )

    # TODO: Save agent steps when orchestrator implements step tracking
    # Current orchestrator implementation doesn't return "steps" key
    # Future implementation should include:
    # - agent_type: AgentType enum (ORCHESTRATOR, DATA_AGENT, RAG_AGENT, SKILL)
    # - step_type: StepType enum (REASONING, TOOL_CALL, TOOL_RESULT, FINAL_ANSWER)
    # - tool_name, content, duration_ms

    # Extract metadata
    metadata = result.get("metadata", {})

    # Track token usage (rough estimation based on message length)
    # TODO: Get actual token counts from LLM provider response
    prompt_tokens = int(len(request.message.split()) * 1.3)  # Rough word-to-token ratio
    completion_tokens = int(len(result["message"].split()) * 1.3)

    TokenTrackingService.track_usage(
        db=db,
        user_id=current_user.id,
        operation=OperationType.CHAT,
        model=settings.default_llm_model or "gpt-4o",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens
    )

    return ChatResponse(
        thread_id=conversation.thread_id,
        message=result["message"],
        sql_queries=metadata.get("sql_queries", []),
        results=metadata.get("results", []),
        success=result.get("success", False)
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream chat responses using Server-Sent Events (SSE).

    Events:
    - data: {"type": "status", "content": "Starting orchestrator..."}
    - data: {"type": "tool_call", "content": {"tool": "data_agent", "args": {...}}}
    - data: {"type": "tool_result", "content": {...}}
    - data: {"type": "token", "content": "word"}
    - data: {"type": "done", "thread_id": "..."}
    - data: {"type": "error", "content": "error message"}
    """
    # Lazy import to avoid loading LangGraph unless needed
    from backend.agents import stream_orchestrator
    from backend.agents.context import AgentContext

    async def event_generator():
        import redis as sync_redis
        redis_client = sync_redis.from_url(settings.redis_url, decode_responses=True)
        active_thread_id = request.thread_id

        try:
            from backend.services.heartbeat_context import build_orchestrator_context

            # Track whether this is a brand-new conversation for title generation
            is_new_conversation = not request.thread_id

            # Get or create conversation
            if request.thread_id:
                conversation = ConversationService.get_conversation_by_thread(
                    db, request.thread_id, current_user.id
                )
                if not conversation:
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Conversation not found'})}\n\n"
                    return
            else:
                conversation = ConversationService.create_conversation(
                    db, current_user.id, title="New Task"
                )

            active_thread_id = conversation.thread_id

            # Save user message
            ConversationService.add_message(db, conversation.id, "user", request.message)

            # Validate requested connection access
            if request.connection_ids:
                accessible = db.query(DatabaseConnection.id).filter(
                    DatabaseConnection.id.in_(request.connection_ids),
                    DatabaseConnection.user_id == current_user.id
                ).all()
                if len(accessible) != len(request.connection_ids):
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Access denied to connections'})}\n\n"
                    return

            # Build orchestrator context (connections, teams, skills, memories)
            ctx = await build_orchestrator_context(
                db=db,
                user=current_user,
                query=request.message,
                connection_ids=request.connection_ids or None,
                thread_id=conversation.thread_id,
            )

            # Fetch conversation history (exclude the just-saved user message)
            history = ConversationService.get_conversation_history(db, conversation.thread_id, current_user.id)
            history = history[:-1]
            # Truncate at last context reset boundary
            for i in range(len(history) - 1, -1, -1):
                if history[i].source == "context_reset":
                    history = history[i + 1:]
                    break

            # Set Redis streaming flag (TTL 5 min safety net)
            redis_client.setex(f"streaming:{active_thread_id}", 300, "sse")

            # Resolve user's preferred LLM provider
            user_provider = get_provider(settings.default_llm_provider)

            # Stream orchestrator execution
            from backend.database.session import SessionLocal
            logger.info("chat_stream: ctx.profile=%s (id=%s)", ctx.profile, getattr(ctx.profile, 'id', 'NONE'))
            final_message = ""
            collected_steps = []
            async for event in stream_orchestrator(request.message, ctx.agent_context, history=history, custom_agents=ctx.custom_agents or None, db_session_factory=SessionLocal, memory_context=ctx.memory_context, user_skills=ctx.user_skills or None, user_memories_context=ctx.user_memories_context, skill_suggestions=ctx.skill_suggestions or None, soul_prompt=ctx.soul_prompt, profile=ctx.profile, llm_provider=user_provider):
                # Forward event to client
                yield f"data: {json.dumps(event)}\n\n"

                # Capture final message for saving
                if event.get("type") == "token":
                    final_message += event.get("content", "")

                # Capture steps from done event
                if event.get("type") == "done" and "steps" in event:
                    collected_steps = event.get("steps", [])

            # Save assistant message (save even if empty — tool-only turns
            # like ask_user_question still need steps persisted)
            if final_message or collected_steps:
                assistant_msg = ConversationService.add_message(db, conversation.id, "assistant", final_message or "")

                # Save agent steps
                if collected_steps:
                    from backend.models.agent_step import AgentStep
                    for i, step in enumerate(collected_steps):
                        agent_step = AgentStep(
                            message_id=assistant_msg.id,
                            step_number=i + 1,
                            agent_type=step.get("agent_type", "unknown"),
                            step_type=step.get("step_type", "unknown"),
                            tool_name=step.get("tool_name"),
                            content=step.get("content", {}),
                            duration_ms=step.get("duration_ms")
                        )
                        db.add(agent_step)
                    db.commit()

            # Generate LLM title for new conversations after streaming completes
            if is_new_conversation and final_message:
                try:
                    title = await _generate_title(request.message, final_message)
                    ConversationService.update_title(db, conversation.id, title)
                    yield f"data: {json.dumps({'type': 'title', 'content': title})}\n\n"
                except Exception as title_err:
                    logger.warning(f"Title generation failed: {title_err}")

            # Generate/update conversation summary
            if final_message:
                try:
                    from backend.services.summary_service import SummaryService
                    summary = await SummaryService.generate_or_update_summary(
                        db, conversation.id, request.message, final_message
                    )
                    token_count = SummaryService.estimate_conversation_tokens(db, conversation.id)
                    token_limit = SummaryService.get_token_limit()
                    yield f"data: {json.dumps({'type': 'summary', 'content': {'text': summary.summary_text, 'updated_at': summary.updated_at.isoformat(), 'token_count': token_count, 'token_limit': token_limit}})}\n\n"
                except Exception as summary_err:
                    logger.warning(f"Summary generation failed: {summary_err}")

            # Clear streaming flag on successful completion
            if active_thread_id:
                try:
                    redis_client.delete(f"streaming:{active_thread_id}")
                except Exception:
                    pass

        except Exception as e:
            # Clear streaming flag on error
            if active_thread_id:
                try:
                    redis_client.delete(f"streaming:{active_thread_id}")
                except Exception:
                    pass
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations")
async def list_conversations(
    archived: bool = Query(False),
    summary: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List conversations for the current user, optionally filtered by archive status.
    Use summary=true for a lightweight response without message content (sidebar listing).
    """
    if not archived:
        ConversationService.get_or_create_permanent_conversation(db, current_user.id)
    conversations = ConversationService.list_conversations(db, current_user.id, archived=archived)
    if summary:
        return ConversationListSummaryResponse(conversations=conversations)
    return ConversationListResponse(conversations=conversations)


@router.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def get_conversation(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific conversation with all messages."""
    conversation = ConversationService.get_conversation_by_thread(
        db, thread_id, current_user.id
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.patch("/conversations/{thread_id}/title")
async def update_conversation_title(
    thread_id: str,
    request: UpdateTitleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the title of a conversation."""
    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    ConversationService.update_title(db, conversation.id, request.title)
    return {"title": request.title}


@router.patch("/conversations/{thread_id}/archive")
async def archive_conversation(
    thread_id: str,
    request: ArchiveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Archive or unarchive a conversation."""
    try:
        conversation = ConversationService.archive_conversation(
            db, thread_id, current_user.id, archived=request.archived
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    return {"thread_id": conversation.thread_id, "is_archived": conversation.is_archived}


@router.get("/conversations/{thread_id}/summary", response_model=ConversationSummaryResponse)
async def get_conversation_summary(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the summary and token usage for a conversation."""
    from backend.services.summary_service import SummaryService

    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    summary = SummaryService.get_summary(db, conversation.id)
    token_count = SummaryService.estimate_conversation_tokens(db, conversation.id)
    token_limit = SummaryService.get_token_limit()

    return {
        "text": summary.summary_text if summary else None,
        "updated_at": summary.updated_at.isoformat() if summary else None,
        "token_count": token_count,
        "token_limit": token_limit,
    }


@router.post("/conversations/{thread_id}/summary/generate", response_model=ConversationSummaryResponse)
async def generate_conversation_summary(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Force-generate a summary from the full conversation history."""
    from backend.services.summary_service import SummaryService

    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    summary = await SummaryService.generate_full_summary(db, conversation.id)
    token_count = SummaryService.estimate_conversation_tokens(db, conversation.id)
    token_limit = SummaryService.get_token_limit()

    return {
        "text": summary.summary_text,
        "updated_at": summary.updated_at.isoformat(),
        "token_count": token_count,
        "token_limit": token_limit,
    }


@router.delete("/conversations/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation and all its messages."""
    try:
        deleted = ConversationService.delete_conversation(db, thread_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/conversations/{thread_id}/streaming")
async def get_streaming_status(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if a conversation is currently being streamed."""
    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    import redis as sync_redis
    redis_client = sync_redis.from_url(settings.redis_url, decode_responses=True)
    is_streaming = redis_client.exists(f"streaming:{thread_id}") > 0
    return {"streaming": is_streaming}


@router.get("/conversations/{thread_id}/messages/{message_id}/steps", response_model=MessageStepsResponse)
async def get_message_steps(
    thread_id: str,
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get agent execution steps for a specific message.

    Returns the full reasoning chain for display in frontend:
    - Reasoning: What the LLM decided to do
    - Tool calls: What tools were invoked
    - Tool results: What came back from tools
    - Final answer: The synthesized response
    """
    # Verify conversation belongs to user
    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get message and verify it belongs to this conversation
    from backend.models.message import Message
    message = db.query(Message).filter(
        Message.id == message_id,
        Message.conversation_id == conversation.id
    ).first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Get steps for this message
    from backend.models.agent_step import AgentStep
    steps = db.query(AgentStep).filter(
        AgentStep.message_id == message_id
    ).order_by(AgentStep.step_number).all()

    return MessageStepsResponse(steps=steps)
