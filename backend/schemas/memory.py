"""Pydantic schemas for memory system."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


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


# User-directed memory schemas

class UserMemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)


class UserMemoryUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class UserMemoryResponse(BaseModel):
    id: str
    content: str
    category: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserMemoryListResponse(BaseModel):
    entries: List[UserMemoryResponse]
    total: int


# Memory settings schemas

class MemorySettingsResponse(BaseModel):
    memory_enabled: bool


class MemorySettingsUpdate(BaseModel):
    memory_enabled: bool
