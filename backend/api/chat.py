from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.chat import ChatRequest, ChatResponse, ConversationResponse, ConversationListResponse, MessageStepsResponse
from backend.services.conversation_service import ConversationService
from backend.agents import run_orchestrator, stream_orchestrator
from backend.agents.context import AgentContext
import json

router = APIRouter(prefix="/chat", tags=["chat"])


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
    # Get or create conversation
    if request.thread_id:
        conversation = ConversationService.get_conversation_by_thread(
            db, request.thread_id, current_user.id
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = ConversationService.create_conversation(
            db, current_user.id, title=request.message[:50]
        )

    # Save user message
    ConversationService.add_message(
        db, conversation.id, "user", request.message
    )

    # Get user's accessible connections
    if request.connection_ids:
        # Verify access
        accessible_connections = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.id.in_(request.connection_ids),
            DatabaseConnection.user_id == current_user.id
        ).all()

        accessible_ids = [conn.id for conn in accessible_connections]

        if len(accessible_ids) != len(request.connection_ids):
            raise HTTPException(
                status_code=403,
                detail="Access denied to one or more connections"
            )
    else:
        # Get all user connections
        accessible_connections = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.user_id == current_user.id
        ).all()
        accessible_ids = [conn.id for conn in accessible_connections]

    # Build AgentContext
    context = AgentContext(
        user_id=current_user.id,
        available_connections=accessible_ids,
        thread_id=conversation.thread_id
    )

    # Run orchestrator
    result = await run_orchestrator(
        user_question=request.message,
        context=context
    )

    # Save assistant message
    assistant_msg = ConversationService.add_message(
        db, conversation.id, "assistant", result["message"]
    )

    # Save agent steps
    steps = result.get("steps", [])
    if steps:
        from backend.models.agent_step import AgentStep
        for i, step in enumerate(steps):
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

    # Extract metadata
    metadata = result.get("metadata", {})

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
    async def event_generator():
        try:
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
                    db, current_user.id, title=request.message[:50]
                )

            # Save user message
            ConversationService.add_message(db, conversation.id, "user", request.message)

            # Get user's accessible connections
            if request.connection_ids:
                accessible_connections = db.query(DatabaseConnection.id).filter(
                    DatabaseConnection.id.in_(request.connection_ids),
                    DatabaseConnection.user_id == current_user.id
                ).all()

                accessible_ids = [conn.id for conn in accessible_connections]

                if len(accessible_ids) != len(request.connection_ids):
                    yield f"data: {json.dumps({'type': 'error', 'content': 'Access denied to connections'})}\n\n"
                    return
            else:
                accessible_connections = db.query(DatabaseConnection.id).filter(
                    DatabaseConnection.user_id == current_user.id
                ).all()
                accessible_ids = [conn.id for conn in accessible_connections]

            # Build AgentContext
            context = AgentContext(
                user_id=current_user.id,
                available_connections=accessible_ids,
                thread_id=conversation.thread_id
            )

            # Stream orchestrator execution
            final_message = ""
            collected_steps = []
            async for event in stream_orchestrator(request.message, context):
                # Forward event to client
                yield f"data: {json.dumps(event)}\n\n"

                # Capture final message for saving
                if event.get("type") == "token":
                    final_message += event.get("content", "")

                # Capture steps from done event
                if event.get("type") == "done" and "steps" in event:
                    collected_steps = event.get("steps", [])

            # Save assistant message
            if final_message:
                assistant_msg = ConversationService.add_message(db, conversation.id, "assistant", final_message)

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

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all conversations for the current user."""
    conversations = ConversationService.list_conversations(db, current_user.id)
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


@router.delete("/conversations/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation and all its messages."""
    deleted = ConversationService.delete_conversation(db, thread_id, current_user.id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


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
