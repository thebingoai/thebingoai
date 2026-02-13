"""Pydantic schemas for memory system."""

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
