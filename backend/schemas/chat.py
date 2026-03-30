from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=50_000)
    connection_ids: List[int] = Field(default_factory=list)  # Connections available to orchestrator
    thread_id: Optional[str] = None  # For continuing conversations


class ChatAttachment(BaseModel):
    file_id: str
    name: str
    type: str
    size: int
    content_type: Optional[str] = None
    storage_key: Optional[str] = None


class ChatMessage(BaseModel):
    id: int
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    source: str = "chat"
    attachments: Optional[List[ChatAttachment]] = None

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    thread_id: str
    message: str
    sql_queries: List[str] = []  # SQL queries executed
    results: List[Dict[str, Any]] = []  # Query results
    success: bool


class ConversationResponse(BaseModel):
    id: int
    thread_id: str
    user_id: str
    title: Optional[str]
    type: str = "task"
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage] = []

    class Config:
        from_attributes = True


class ConversationListItem(BaseModel):
    """Lightweight conversation item for sidebar listing (no messages)."""
    id: int
    thread_id: str
    user_id: str
    title: Optional[str]
    type: str = "task"
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]


class ConversationListSummaryResponse(BaseModel):
    conversations: List[ConversationListItem]


class AgentStepResponse(BaseModel):
    """Agent execution step for frontend display."""
    id: int
    step_number: int
    agent_type: str
    step_type: str
    tool_name: Optional[str]
    content: Dict[str, Any]
    duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class MessageStepsResponse(BaseModel):
    """Response containing all steps for a message."""
    steps: List[AgentStepResponse]


class UpdateTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class ArchiveRequest(BaseModel):
    archived: bool


class ConversationSummaryResponse(BaseModel):
    text: Optional[str] = None
    updated_at: Optional[datetime] = None
    token_count: int
    token_limit: int
