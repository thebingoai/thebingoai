"""Memory API endpoints."""

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

    memories = await retriever.storage.retrieve_memories(
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
    await retriever.storage.delete_user_memories(current_user.id)
