"""Memory API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.user_memory import UserMemory
from backend.schemas.memory import (
    MemoryGenerateRequest, MemorySearchRequest,
    MemorySearchResponse, MemoryGenerateResponse,
    UserMemoryCreate, UserMemoryUpdate, UserMemoryResponse, UserMemoryListResponse,
    MemorySettingsResponse, MemorySettingsUpdate,
    MemoryHeatmapEntry, MemoryHeatmapResponse,
    SoulResponse, SoulUpdate,
)
from backend.memory.storage import MemoryStorage
from backend.tasks.memory_tasks import generate_user_memory
from backend.memory.retriever import MemoryRetriever
from datetime import datetime

router = APIRouter(prefix="/memory", tags=["memory"])

_MAX_ENTRIES = 50


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
    """Delete all auto-generated memories for current user."""
    retriever = MemoryRetriever()
    await retriever.storage.delete_user_memories(current_user.id)


# ── Heatmap ───────────────────────────────────────────────────────────────────

@router.get("/heatmap", response_model=MemoryHeatmapResponse)
async def get_memory_heatmap(
    current_user: User = Depends(get_current_user)
):
    """Get daily conversation memory activity for heatmap visualization."""
    storage = MemoryStorage()
    entries = storage.list_memory_dates(current_user.id)

    total_conversations = sum(e["count"] for e in entries)
    return MemoryHeatmapResponse(
        data=[MemoryHeatmapEntry(date=e["date"], count=e["count"]) for e in entries],
        total_days=len(entries),
        total_conversations=total_conversations,
    )


# ── User-directed memory entries ──────────────────────────────────────────────

@router.get("/entries", response_model=UserMemoryListResponse)
async def list_memory_entries(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all user-directed memory entries."""
    entries = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == current_user.id)
        .order_by(UserMemory.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = db.query(UserMemory).filter(UserMemory.user_id == current_user.id).count()
    return UserMemoryListResponse(entries=entries, total=total)


@router.post("/entries", response_model=UserMemoryResponse, status_code=201)
async def create_memory_entry(
    payload: UserMemoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new user-directed memory entry (max 50 per user)."""
    count = db.query(UserMemory).filter(UserMemory.user_id == current_user.id).count()
    if count >= _MAX_ENTRIES:
        raise HTTPException(
            status_code=422,
            detail=f"Memory limit reached ({_MAX_ENTRIES} entries). Delete some entries first."
        )

    entry = UserMemory(
        user_id=current_user.id,
        content=payload.content,
        category=payload.category,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/entries/{entry_id}", response_model=UserMemoryResponse)
async def update_memory_entry(
    entry_id: str,
    payload: UserMemoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a user-directed memory entry."""
    entry = db.query(UserMemory).filter(
        UserMemory.id == entry_id,
        UserMemory.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Memory entry not found")

    if payload.content is not None:
        entry.content = payload.content
    if payload.category is not None:
        entry.category = payload.category
    if payload.is_active is not None:
        entry.is_active = payload.is_active

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_memory_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user-directed memory entry."""
    entry = db.query(UserMemory).filter(
        UserMemory.id == entry_id,
        UserMemory.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    db.delete(entry)
    db.commit()


# ── Memory settings ───────────────────────────────────────────────────────────

@router.get("/settings", response_model=MemorySettingsResponse)
async def get_memory_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the user's memory settings."""
    prefs = current_user.preferences or {}
    return MemorySettingsResponse(memory_enabled=prefs.get("memory_enabled", True))


@router.put("/settings", response_model=MemorySettingsResponse)
async def update_memory_settings(
    payload: MemorySettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the user's memory settings."""
    prefs = dict(current_user.preferences or {})
    prefs["memory_enabled"] = payload.memory_enabled
    current_user.preferences = prefs
    db.commit()
    return MemorySettingsResponse(memory_enabled=payload.memory_enabled)


# ── Soul ──────────────────────────────────────────────────────────────────────

@router.get("/soul", response_model=SoulResponse)
async def get_soul(
    current_user: User = Depends(get_current_user),
):
    """Get the current user's soul prompt and version."""
    return SoulResponse(
        soul_prompt=current_user.soul_prompt,
        soul_version=current_user.soul_version or 0,
    )


@router.put("/soul", response_model=SoulResponse)
async def update_soul(
    payload: SoulUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually update the user's soul prompt (direct edit from UI)."""
    current_user.soul_prompt = payload.soul_prompt or None
    current_user.soul_version = (current_user.soul_version or 0) + 1
    db.commit()
    return SoulResponse(
        soul_prompt=current_user.soul_prompt,
        soul_version=current_user.soul_version,
    )


@router.delete("/soul", status_code=204)
async def delete_soul(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset the user's soul to empty."""
    current_user.soul_prompt = None
    current_user.soul_version = 0
    db.commit()
