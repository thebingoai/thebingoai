from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class QueryRequest(BaseModel):
    """POST /api/query request body."""
    query: str = Field(..., min_length=1, max_length=10000)
    namespace: str = "default"
    top_k: int = Field(default=5, ge=1, le=100)
    filter: Optional[dict] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "What are embeddings?",
            "namespace": "default",
            "top_k": 5
        }
    })

class AskRequest(BaseModel):
    """POST /api/ask request body."""
    question: str = Field(..., min_length=1, max_length=10000)
    namespace: str = "default"
    top_k: int = Field(default=5, ge=1, le=20)
    provider: str = Field(default="openai", pattern="^(openai|anthropic|ollama)$")
    model: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    thread_id: Optional[str] = None  # For LangGraph conversation memory

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "question": "Summarize my notes on embeddings",
            "namespace": "personal",
            "provider": "openai",
            "stream": True,
            "thread_id": "abc123-def456"
        }
    })
