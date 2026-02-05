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
