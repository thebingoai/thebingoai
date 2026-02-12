# Phase 05: Chat API with Orchestrator Integration

## Objective

Build simplified chat API that integrates authentication, orchestrator agent, SSE streaming, and conversation persistence. Orchestrator routes to sub-agents (Data Agent, RAG Agent) and skills based on user intent.

## Prerequisites

- Phase 02: Authentication (user context)
- Phase 03: Database Connectors (cached schema JSON)
- Phase 04: Agent Orchestration (Orchestrator + Data Agent + RAG wrapper + Skills)

## Files to Create

### API & Schemas
- `backend/api/chat.py` - Chat endpoints with SSE streaming
- `backend/schemas/chat.py` - Chat request/response schemas

### Services
- `backend/services/conversation_service.py` - Conversation and message persistence

### Tests
- `backend/tests/test_chat_api.py` - Integration tests

## Files to Modify

- `backend/api/routes.py` - Register chat routes
- `backend/models/conversation.py` - Add helper methods (if needed)

## Implementation Details

### 1. Chat Schemas (backend/schemas/chat.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    connection_ids: List[int] = Field(default_factory=list)  # Connections available (orchestrator decides which to use)
    thread_id: Optional[str] = None  # For continuing conversations

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    thread_id: str
    message: str
    sql_queries: List[str] = []  # All SQL queries executed by agent
    results: List[Dict[str, Any]] = []  # All query results
    success: bool

class ConversationResponse(BaseModel):
    id: int
    thread_id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage] = []

    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]

class AgentStepResponse(BaseModel):
    """Agent execution step for frontend display."""
    id: int
    step_number: int
    agent_type: str  # "orchestrator" | "data_agent" | "rag_agent" | "skill"
    step_type: str  # "reasoning" | "tool_call" | "tool_result" | "final_answer"
    tool_name: Optional[str]
    content: Dict[str, Any]
    duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

class MessageStepsResponse(BaseModel):
    """Response containing all steps for a message."""
    steps: List[AgentStepResponse]
```

### 2. Conversation Service (backend/services/conversation_service.py)

```python
from sqlalchemy.orm import Session
from backend.models.conversation import Conversation
from backend.models.message import Message
from typing import Optional, List
import uuid

class ConversationService:
    """Service for managing conversations and messages."""

    @staticmethod
    def create_conversation(db: Session, user_id: str, title: Optional[str] = None) -> Conversation:
        """Create a new conversation."""
        thread_id = str(uuid.uuid4())

        conversation = Conversation(
            thread_id=thread_id,
            user_id=user_id,
            title=title or "New Chat"
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        return conversation

    @staticmethod
    def get_conversation_by_thread(db: Session, thread_id: str, user_id: str) -> Optional[Conversation]:
        """Get conversation by thread ID."""
        return db.query(Conversation).filter(
            Conversation.thread_id == thread_id,
            Conversation.user_id == user_id
        ).first()

    @staticmethod
    def add_message(db: Session, conversation_id: int, role: str, content: str) -> Message:
        """Add a message to a conversation."""
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )

        db.add(message)
        db.commit()
        db.refresh(message)

        return message

    @staticmethod
    def get_conversation_history(db: Session, thread_id: str, user_id: str) -> List[Message]:
        """Get all messages in a conversation."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if not conversation:
            return []

        return db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(Message.timestamp).all()

    @staticmethod
    def list_conversations(db: Session, user_id: str, limit: int = 50) -> List[Conversation]:
        """List all conversations for a user."""
        return db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.updated_at.desc()).limit(limit).all()

    @staticmethod
    def update_conversation_title(db: Session, thread_id: str, user_id: str, title: str):
        """Update conversation title."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if conversation:
            conversation.title = title
            db.commit()
            db.refresh(conversation)

        return conversation

    @staticmethod
    def delete_conversation(db: Session, thread_id: str, user_id: str) -> bool:
        """Delete a conversation and all its messages."""
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user_id)

        if conversation:
            db.delete(conversation)
            db.commit()
            return True

        return False
```

### 3. Chat API (backend/api/chat.py)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.chat import ChatRequest, ChatResponse, ConversationResponse, ConversationListResponse, MessageStepsResponse
from backend.services.conversation_service import ConversationService
from backend.agents.orchestrator import run_orchestrator, stream_orchestrator
from backend.agents.context import AgentContext
from typing import List
import json
import asyncio

router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process a chat message and execute orchestrator agent.

    Flow:
    1. Get or create conversation
    2. Save user message
    3. Verify user has access to requested connections
    4. Build AgentContext with user context
    5. Invoke orchestrator (routes to Data Agent, RAG Agent, or skills)
    6. Save orchestrator response
    7. Return results

    - **message**: User's natural language question
    - **connection_ids**: List of database connections available (orchestrator decides which to use based on intent)
    - **thread_id**: Optional thread ID to continue conversation
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
        # Verify user has access to requested connections
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
        # No specific connections requested - get all user connections
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

    # Run orchestrator (routes to Data Agent, RAG Agent, or skills based on intent)
    result = await run_orchestrator(
        user_question=request.message,
        context=context
    )

    # Build response message
    response_content = result["message"]

    # Save assistant message
    assistant_msg = ConversationService.add_message(
        db, conversation.id, "assistant", response_content
    )

    # Save agent steps (NEW: Phase 04 integration)
    steps = result.get("steps", [])
    if steps:
        from backend.models.agent_step import AgentStep
        for i, step in enumerate(steps):
            agent_step = AgentStep(
                message_id=assistant_msg.id,
                step_number=i + 1,
                agent_type=step.agent_type,
                step_type=step.step_type,
                tool_name=step.tool_name,
                content=step.content,
                duration_ms=step.duration_ms
            )
            db.add(agent_step)
        db.commit()

    # Extract metadata from orchestrator result
    metadata = result.get("metadata", {})

    return ChatResponse(
        thread_id=conversation.thread_id,
        message=response_content,
        sql_queries=metadata.get("sql_queries", []),  # If Data Agent was invoked
        results=metadata.get("results", []),  # If Data Agent was invoked
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

    Orchestrator streams progress as it routes to sub-agents and executes tools.

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
            final_message = None
            collected_steps = []  # NEW: Collect steps during streaming
            async for event in stream_orchestrator(request.message, context):
                # Forward event to client
                yield f"data: {json.dumps(event)}\n\n"

                # Capture final message for saving
                if event.get("type") == "token":
                    if final_message is None:
                        final_message = event.get("content", "")
                    else:
                        final_message += event.get("content", "")

                # NEW: Capture steps from done event
                if event.get("type") == "done" and "steps" in event:
                    collected_steps = event.get("steps", [])

            # Save assistant message
            if final_message:
                assistant_msg = ConversationService.add_message(db, conversation.id, "assistant", final_message)

                # NEW: Save agent steps
                if collected_steps:
                    from backend.models.agent_step import AgentStep
                    for i, step in enumerate(collected_steps):
                        agent_step = AgentStep(
                            message_id=assistant_msg.id,
                            step_number=i + 1,
                            agent_type=step.agent_type,
                            step_type=step.step_type,
                            tool_name=step.tool_name,
                            content=step.content,
                            duration_ms=step.duration_ms
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
    """List all conversations for current user."""
    conversations = ConversationService.list_conversations(db, current_user.id)
    return ConversationListResponse(conversations=conversations)

@router.get("/conversations/{thread_id}", response_model=ConversationResponse)
async def get_conversation(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific conversation with all messages."""
    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation

@router.delete("/conversations/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation."""
    success = ConversationService.delete_conversation(db, thread_id, current_user.id)

    if not success:
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

    Returns the full reasoning chain (thinking steps) for display in frontend.
    Steps include:
    - Reasoning: What the LLM decided to do
    - Tool calls: What tools were invoked
    - Tool results: What came back from tools
    - Final answer: The synthesized response

    NEW: Phase 04 integration for agent step logging
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
```

### 4. Register Routes (backend/api/routes.py)

```python
from backend.api import chat  # Add import

# In create_api_router():
api_router.include_router(chat.router)
```

## Testing & Verification

### Manual Testing Steps

1. **Test data question** (routed to Data Agent):
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Show me all users",
       "connection_ids": [1]
     }'
   ```

2. **Test document question** (routed to RAG Agent):
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "What does the documentation say about authentication?",
       "connection_ids": []
     }'
   ```

3. **Test orchestrator routing** (auto-detects intent):
   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "How many users do we have, and what do the docs say about them?",
       "connection_ids": [1]
     }'
   ```

3. **Test SSE streaming**:
   ```bash
   curl -N -X POST http://localhost:8000/api/chat/stream \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Count total orders",
       "connection_ids": [1]
     }'
   ```

3. **Test conversation persistence**:
   - Send message, get thread_id
   - Send another message with same thread_id
   - Verify conversation history via GET /api/chat/conversations/{thread_id}

## MCP Browser Testing

Test streaming in browser:

```javascript
const eventSource = new EventSource('/api/chat/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data.content);
};
```

## Code Review Checklist

- [ ] Auth required on all endpoints
- [ ] Conversation isolation (user can't access other users' chats)
- [ ] SSE streaming works correctly with orchestrator events
- [ ] Messages persisted to database
- [ ] Thread IDs are UUIDs (non-guessable)
- [ ] Error handling for invalid connection_ids
- [ ] Connection authorization enforced (user can only access their connections)
- [ ] AgentContext built correctly with user context
- [ ] Orchestrator routes to correct sub-agents (Data Agent, RAG Agent)
- [ ] Multiple connection_ids supported (orchestrator decides which to use)
- [ ] Tool results captured from orchestrator metadata

## Done Criteria

1. Can send chat message with connection_ids (for Data Agent)
2. Can send chat message without connection_ids (for RAG Agent)
3. AgentContext built correctly with user context
4. Orchestrator routes data questions to Data Agent
5. Orchestrator routes document questions to RAG Agent
6. SSE streaming works and shows orchestrator progress (tool_call, tool_result, token, done)
7. Conversations persisted to PostgreSQL
8. Can list conversations
9. Can get conversation history
10. Can delete conversations
11. Auth required on all endpoints
12. Connection authorization enforced
13. Integration tests pass for orchestrator routing

## Rollback Plan

If this phase fails:
1. Remove backend/api/chat.py
2. Remove backend/schemas/chat.py
3. Remove backend/services/conversation_service.py
4. Remove chat routes from backend/api/routes.py
