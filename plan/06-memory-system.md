# Phase 06: Memory System

## Objective

Build daily memory generation system that summarizes user interactions, stores summaries in Qdrant, and retrieves relevant context during query generation.

## Prerequisites

- Phase 05: Chat API (conversations to summarize)

## Files to Create

### Memory System
- `backend/memory/__init__.py` - Export memory functions
- `backend/memory/generator.py` - Daily summary generation
- `backend/memory/retriever.py` - Context retrieval from Qdrant
- `backend/memory/storage.py` - Qdrant storage helpers (uses backend/vectordb/qdrant.py)

### Celery Tasks
- `backend/tasks/memory_tasks.py` - Celery task for daily memory generation

### API
- `backend/api/memory.py` - Memory endpoints (trigger, view, search)
- `backend/schemas/memory.py` - Memory schemas

### Tests
- `backend/tests/test_memory.py` - Unit tests

## Files to Modify

- `backend/api/routes.py` - Register memory routes
- `backend/agents/query_agent/nodes.py` - Add memory retrieval to SQL generation

## Implementation Details

### 1. Memory Storage (backend/memory/storage.py)

```python
from backend.vectordb.qdrant import upsert_vectors, query_vectors, delete_by_filter
from backend.embedder.openai import OpenAIEmbedder
from typing import List, Dict, Any
from datetime import datetime

class MemoryStorage:
    """Store and retrieve memories from Qdrant via shared vectordb module."""

    def __init__(self):
        self.embedder = OpenAIEmbedder()

    async def store_memory(
        self,
        user_id: str,
        memory_text: str,
        date: datetime,
        metadata: Dict[str, Any]
    ) -> str:
        """Store a memory in Qdrant memories collection."""
        embedding = await self.embedder.embed_text(memory_text)
        memory_id = f"memory:{user_id}:{date.strftime('%Y-%m-%d')}"

        # Uses namespace pattern — qdrant module routes to memories collection
        namespace = f"memory:user-{user_id}"

        vectors = [{
            "id": memory_id,
            "values": embedding,
            "metadata": {
                "user_id": user_id,
                "memory_text": memory_text,
                "date": date.isoformat(),
                **metadata
            }
        }]

        await upsert_vectors(vectors, namespace=namespace)
        return memory_id

    async def retrieve_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant memories via semantic search."""
        query_embedding = await self.embedder.embed_text(query)
        namespace = f"memory:user-{user_id}"

        results = await query_vectors(query_embedding, namespace=namespace, top_k=top_k)

        memories = []
        for match in results:
            memories.append({
                "id": match["id"],
                "score": match["score"],
                "text": match["metadata"].get("memory_text", ""),
                "date": match["metadata"].get("date"),
                "metadata": {k: v for k, v in match["metadata"].items()
                           if k not in ["memory_text", "date", "user_id",
                                       "tenant_id", "original_id"]}
            })
        return memories

    async def delete_user_memories(self, user_id: str):
        """Delete all memories for a user."""
        from backend.config import settings
        await delete_by_filter(
            collection=settings.qdrant_memories_collection,
            filter={"tenant_id": user_id}
        )
```

### 2. Memory Generator (backend/memory/generator.py)

```python
from sqlalchemy.orm import Session
from backend.services.conversation_service import ConversationService
from backend.llm.factory import get_llm_provider
from backend.config import settings
from backend.memory.storage import MemoryStorage
from langchain_core.messages import SystemMessage, HumanMessage
from datetime import datetime, timedelta
from typing import Dict, Any
import json

MEMORY_GENERATION_PROMPT = """You are a memory system that summarizes user interactions with a Business Intelligence agent.

Given the user's conversations from the past day, generate a concise summary that captures:
1. Common questions or topics the user asked about
2. Database tables/schemas the user frequently queries
3. Any patterns in the user's query style or preferences
4. Errors or corrections that occurred
5. Key insights or learnings

Conversations:
{conversations}

Generate a JSON summary with the following structure:
{{
  "summary": "Natural language summary of the day's interactions",
  "common_questions": ["Question 1", "Question 2", ...],
  "common_tables": ["table1", "table2", ...],
  "query_patterns": ["pattern1", "pattern2", ...],
  "corrections": ["correction1", "correction2", ...],
  "insights": ["insight1", "insight2", ...]
}}

Return ONLY the JSON, no additional text."""

class MemoryGenerator:
    """Generate daily memory summaries for users."""

    def __init__(self):
        self.storage = MemoryStorage()
        self.llm = get_llm_provider(settings.default_llm_provider)

    def generate_daily_memory(self, db: Session, user_id: str, date: datetime) -> Dict[str, Any]:
        """
        Generate a daily memory summary for a user.

        Args:
            db: Database session
            user_id: User ID
            date: Date to generate memory for

        Returns:
            Memory summary dictionary
        """
        # Get all conversations from the day
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        conversations = ConversationService.list_conversations(db, user_id, limit=100)

        # Filter to conversations from the target date
        daily_conversations = [
            conv for conv in conversations
            if start_of_day <= conv.created_at < end_of_day
        ]

        if not daily_conversations:
            return {
                "summary": "No interactions on this day",
                "common_questions": [],
                "common_tables": [],
                "query_patterns": [],
                "corrections": [],
                "insights": []
            }

        # Build conversation text
        conversation_texts = []
        for conv in daily_conversations:
            messages = ConversationService.get_conversation_history(
                db, conv.thread_id, user_id
            )
            conv_text = f"Conversation (ID: {conv.thread_id}):\n"
            for msg in messages:
                conv_text += f"  {msg.role}: {msg.content}\n"
            conversation_texts.append(conv_text)

        all_conversations = "\n\n".join(conversation_texts)

        # Generate summary using LLM
        prompt = MEMORY_GENERATION_PROMPT.format(conversations=all_conversations)
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the memory summary")
        ]

        response = self.llm.chat(messages)

        # Parse JSON response
        try:
            summary = json.loads(response)
        except json.JSONDecodeError:
            # Fallback if LLM doesn't return valid JSON
            summary = {
                "summary": response[:500],  # First 500 chars
                "common_questions": [],
                "common_tables": [],
                "query_patterns": [],
                "corrections": [],
                "insights": []
            }

        # Store in Qdrant
        memory_text = summary["summary"]
        metadata = {
            "query_count": len(daily_conversations),
            "common_tables": json.dumps(summary.get("common_tables", [])),
            "query_patterns": json.dumps(summary.get("query_patterns", []))
        }

        memory_id = self.storage.store_memory(
            user_id=user_id,
            memory_text=memory_text,
            date=date,
            metadata=metadata
        )

        summary["memory_id"] = memory_id
        summary["date"] = date.isoformat()

        return summary
```

### 3. Memory Retriever (backend/memory/retriever.py)

```python
from backend.memory.storage import MemoryStorage
from typing import List, Dict, Any

class MemoryRetriever:
    """Retrieve relevant memories for query generation."""

    def __init__(self):
        self.storage = MemoryStorage()

    def get_relevant_context(
        self,
        user_id: str,
        query: str,
        top_k: int = 3
    ) -> str:
        """
        Get relevant memory context for a query.

        Args:
            user_id: User ID
            query: User's query
            top_k: Number of memories to retrieve

        Returns:
            Formatted context string
        """
        memories = self.storage.retrieve_memories(user_id, query, top_k)

        if not memories:
            return ""

        context_parts = ["=== Relevant Past Interactions ===\n"]

        for i, memory in enumerate(memories, 1):
            context_parts.append(f"{i}. {memory['date']} (relevance: {memory['score']:.2f})")
            context_parts.append(f"   {memory['text']}\n")

        return "\n".join(context_parts)
```

### 4. Celery Task (backend/tasks/memory_tasks.py)

```python
from celery import shared_task
from backend.database.session import SessionLocal
from backend.memory.generator import MemoryGenerator
from backend.models.user import User
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@shared_task(name="generate_daily_memories")
def generate_daily_memories():
    """
    Celery task to generate daily memories for all users.

    Runs daily at midnight (configured in Celery beat schedule).
    """
    db = SessionLocal()
    generator = MemoryGenerator()

    try:
        # Get all users
        users = db.query(User).all()
        yesterday = datetime.utcnow() - timedelta(days=1)

        for user in users:
            try:
                logger.info(f"Generating memory for user {user.id}")
                summary = generator.generate_daily_memory(db, user.id, yesterday)
                logger.info(f"Memory generated: {summary['memory_id']}")
            except Exception as e:
                logger.error(f"Failed to generate memory for user {user.id}: {str(e)}")

    finally:
        db.close()

@shared_task(name="generate_user_memory")
def generate_user_memory(user_id: str, date_str: str):
    """
    Generate memory for a specific user and date.

    Args:
        user_id: User ID
        date_str: Date string in ISO format
    """
    db = SessionLocal()
    generator = MemoryGenerator()

    try:
        date = datetime.fromisoformat(date_str)
        summary = generator.generate_daily_memory(db, user_id, date)
        return summary
    finally:
        db.close()
```

### 5. Memory API (backend/api/memory.py)

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.memory import (
    MemoryGenerateRequest, MemorySearchRequest,
    MemorySearchResponse, MemoryGenerateResponse
)
from backend.tasks.memory_tasks import generate_user_memory
from backend.memory.retriever import MemoryRetriever
from datetime import datetime

router = APIRouter(prefix="/memory", tags=["memory"])

@router.post("/generate", response_model=MemoryGenerateResponse)
async def trigger_memory_generation(
    request: MemoryGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger memory generation for a specific date.

    - **date**: Date to generate memory for (ISO format)
    """
    try:
        date = datetime.fromisoformat(request.date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")

    # Trigger Celery task
    task = generate_user_memory.delay(current_user.id, date.isoformat())

    return MemoryGenerateResponse(
        task_id=task.id,
        message="Memory generation started"
    )

@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Search for relevant memories.

    - **query**: Search query
    - **top_k**: Number of results to return (default: 5)
    """
    retriever = MemoryRetriever()

    memories = retriever.storage.retrieve_memories(
        user_id=current_user.id,
        query=request.query,
        top_k=request.top_k
    )

    return MemorySearchResponse(memories=memories)

@router.delete("", status_code=204)
async def delete_all_memories(
    current_user: User = Depends(get_current_user)
):
    """Delete all memories for current user."""
    retriever = MemoryRetriever()
    retriever.storage.delete_user_memories(current_user.id)
```

### 6. Memory Schemas (backend/schemas/memory.py)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class MemoryGenerateRequest(BaseModel):
    date: str = Field(..., description="Date in ISO format (YYYY-MM-DD)")

class MemoryGenerateResponse(BaseModel):
    task_id: str
    message: str

class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)

class MemorySearchResponse(BaseModel):
    memories: List[Dict[str, Any]]
```

### 7. Update Query Agent (backend/agents/query_agent/nodes.py)

Add memory retrieval to SQL generation:

```python
from backend.memory.retriever import MemoryRetriever

def generate_sql_node(state: QueryState) -> dict:
    """Generate SQL query with memory context."""
    # ... existing code ...

    # Add memory context
    retriever = MemoryRetriever()
    memory_context = retriever.get_relevant_context(
        user_id=state["user_id"],
        query=state["user_question"],
        top_k=3
    )

    # Prepend memory context to prompt
    if memory_context:
        prompt = memory_context + "\n\n" + prompt

    # ... rest of existing code ...
```

## Testing & Verification

Manual testing:
1. Create conversations via Chat API
2. Trigger memory generation: `POST /api/memory/generate`
3. Search memories: `POST /api/memory/search`
4. Verify memory influences query generation

## MCP Browser Testing

N/A - Backend only

## Code Review Checklist

- [ ] Memories stored in Qdrant memories collection with tenant_id isolation
- [ ] Memory generation handles empty conversation days
- [ ] Celery task has proper error handling
- [ ] Memory retrieval uses semantic search
- [ ] Memory context prepended to SQL generation prompt
- [ ] Can delete all user memories

## Done Criteria

1. Daily memory generation Celery task works
2. Memories stored in Qdrant memories collection with tenant_id filtering
3. Memory search returns relevant results
4. Memory context included in query generation
5. API endpoints work (generate, search, delete)
6. Unit tests pass

## Rollback Plan

If this phase fails:
1. Remove backend/memory/ directory
2. Remove backend/tasks/memory_tasks.py
3. Remove memory routes
4. Revert query agent changes
