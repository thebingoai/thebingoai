# Pydantic Models

Complete, copy-paste ready Pydantic models for requests, responses, and job handling.

---

## Create `backend/models/__init__.py`

```python
from backend.models.requests import *
from backend.models.responses import *
from backend.models.job import *
```

---

## Create `backend/models/requests.py`

```python
from pydantic import BaseModel, Field
from typing import Optional

class UploadRequest(BaseModel):
    """Multipart form data - handled separately, this is for reference."""
    namespace: str = "default"
    tags: str = ""
    webhook_url: Optional[str] = None
    force_async: bool = False

class QueryRequest(BaseModel):
    """POST /api/query request body."""
    query: str = Field(..., min_length=1, max_length=10000)
    namespace: str = "default"
    top_k: int = Field(default=5, ge=1, le=100)
    filter: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are embeddings?",
                "namespace": "default",
                "top_k": 5
            }
        }

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

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Summarize my notes on embeddings",
                "namespace": "personal",
                "provider": "openai",
                "stream": True,
                "thread_id": "abc123-def456"
            }
        }
```

---

## Create `backend/models/responses.py`

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class HealthResponse(BaseModel):
    status: str

class DetailedHealthResponse(BaseModel):
    status: str
    checks: dict

class UploadResponse(BaseModel):
    status: str  # "success" or "queued"
    file_name: str
    chunks_created: Optional[int] = None
    vectors_upserted: Optional[int] = None
    namespace: str
    job_id: Optional[str] = None
    message: Optional[str] = None
    webhook_url: Optional[str] = None

class QueryResult(BaseModel):
    id: str
    score: float
    source: str
    chunk_index: int
    text: str
    created_at: Optional[str] = None

class QueryResponse(BaseModel):
    query: str
    results: list[QueryResult]
    namespace: str
    total_results: int

class SourceInfo(BaseModel):
    source: str
    chunk_index: int
    score: float

class AskResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    provider: str
    model: str
    thread_id: Optional[str] = None  # Return thread_id for continuation
    has_context: bool = True

class ProviderInfo(BaseModel):
    name: str
    available: bool
    models: list[str]
    error: Optional[str] = None

class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]
    default: dict

class IndexStats(BaseModel):
    name: str
    total_vectors: int
    dimension: int
    namespaces: dict

class StatusResponse(BaseModel):
    status: str
    index: IndexStats
    embedding_model: str
```

---

## Create `backend/models/job.py`

```python
from enum import Enum
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobResult(BaseModel):
    file_name: str
    chunks_created: int
    vectors_upserted: int
    namespace: str

class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    file_name: str
    namespace: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    chunks_total: Optional[int] = None
    chunks_processed: Optional[int] = None
    error: Optional[str] = None
    result: Optional[JobResult] = None

    class Config:
        use_enum_values = True

class JobListResponse(BaseModel):
    jobs: list[JobInfo]
    count: int
```

---

## Related Files

- [cli-modules.md](./cli-modules.md) - CLI API client uses these models
- [backend-api.md](./backend-api.md) - API endpoints use these models
- [langgraph.md](./langgraph.md) - LangGraph workflow uses thread_id from AskRequest
