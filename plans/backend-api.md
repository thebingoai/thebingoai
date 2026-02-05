# Backend API Routes & Endpoints

Complete implementations for FastAPI routes, endpoints, and SSE streaming.

---

## 1. API Routes

### Create `backend/api/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/api/routes.py`

```python
from fastapi import APIRouter
from backend.api import upload, query, chat, status, jobs

router = APIRouter()

# Upload
router.post("/upload", tags=["upload"])(upload.upload_file)

# Query
router.post("/query", tags=["query"])(query.query)
router.get("/search", tags=["query"])(query.search)

# Chat/RAG
router.post("/ask", tags=["chat"])(chat.ask)
router.get("/providers", tags=["chat"])(chat.list_providers)

# Conversation Memory (LangGraph)
router.get("/conversation/{thread_id}", tags=["chat"])(chat.get_history)
router.delete("/conversation/{thread_id}", tags=["chat"])(chat.delete_history)

# Status
router.get("/status", tags=["status"])(status.get_status)

# Jobs
router.get("/jobs", tags=["jobs"])(jobs.list_all_jobs)
router.get("/jobs/{job_id}", tags=["jobs"])(jobs.get_job_status)
```

---

## 2. Upload Endpoint

### Create `backend/api/upload.py`

```python
import uuid
from datetime import datetime
from fastapi import UploadFile, File, Form, HTTPException
from typing import Optional
from backend.config import settings
from backend.parser.markdown import chunk_markdown, count_tokens
from backend.embedder.openai import embed_batch
from backend.vectordb.pinecone import upsert_vectors
from backend.services.job_store import create_job
from backend.tasks.upload_tasks import process_upload_async
from backend.models.responses import UploadResponse
import logging

logger = logging.getLogger(__name__)

async def upload_file(
    file: UploadFile = File(...),
    namespace: str = Form("default"),
    tags: str = Form(""),
    webhook_url: Optional[str] = Form(None),
    force_async: str = Form("false")
) -> UploadResponse:
    """
    Upload and index a markdown file.

    Small files process synchronously, large files are queued.
    """
    # Validate file
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(400, "Only .md files are supported")

    content = await file.read()
    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be valid UTF-8 text")

    file_size = len(content)
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    should_async = force_async.lower() == "true"

    # Determine if async processing needed
    if not should_async:
        if file_size > settings.async_file_size_threshold:
            should_async = True
        else:
            estimated_tokens = count_tokens(content_str)
            estimated_chunks = estimated_tokens // int(settings.chunk_size * 0.8)
            if estimated_chunks > settings.async_chunk_count_threshold:
                should_async = True

    if should_async:
        # Queue for async processing
        job_id = str(uuid.uuid4())
        create_job(job_id, file.filename, namespace)

        process_upload_async.delay(
            job_id=job_id,
            file_content=content_str,
            file_name=file.filename,
            namespace=namespace,
            tags=tags_list,
            webhook_url=webhook_url
        )

        return UploadResponse(
            status="queued",
            file_name=file.filename,
            namespace=namespace,
            job_id=job_id,
            message="File queued for processing",
            webhook_url=webhook_url
        )

    # Sync processing
    logger.info(f"Processing {file.filename} synchronously")

    # 1. Chunk
    chunks = chunk_markdown(content_str, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise HTTPException(400, "No content to index in file")

    # 2. Embed
    chunk_texts = [c["text"] for c in chunks]
    embeddings = await embed_batch(chunk_texts)

    # 3. Prepare vectors
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vectors.append({
            "id": f"{file.filename}#chunk-{i}",
            "values": embedding,
            "metadata": {
                "source": file.filename,
                "chunk_index": i,
                "text": chunk["text"],
                "tags": tags_list,
                "created_at": datetime.utcnow().isoformat()
            }
        })

    # 4. Upsert
    result = await upsert_vectors(vectors, namespace)

    return UploadResponse(
        status="success",
        file_name=file.filename,
        chunks_created=len(chunks),
        vectors_upserted=result.get("upserted_count", len(chunks)),
        namespace=namespace
    )
```

---

## 3. Query Endpoint

### Create `backend/api/query.py`

```python
from fastapi import Query, HTTPException
from typing import Optional
from backend.models.requests import QueryRequest
from backend.models.responses import QueryResponse, QueryResult
from backend.embedder.openai import embed_text
from backend.vectordb.pinecone import query_vectors
import logging

logger = logging.getLogger(__name__)

async def query(request: QueryRequest) -> QueryResponse:
    """Vector similarity search."""
    # Embed the query
    query_embedding = await embed_text(request.query)

    # Search Pinecone
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=request.namespace,
        top_k=request.top_k,
        filter=request.filter
    )

    # Format results
    formatted_results = []
    for r in results:
        formatted_results.append(QueryResult(
            id=r["id"],
            score=round(r["score"], 4),
            source=r["metadata"].get("source", "unknown"),
            chunk_index=r["metadata"].get("chunk_index", 0),
            text=r["metadata"].get("text", ""),
            created_at=r["metadata"].get("created_at")
        ))

    return QueryResponse(
        query=request.query,
        results=formatted_results,
        namespace=request.namespace,
        total_results=len(formatted_results)
    )

async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    namespace: str = Query("default", description="Namespace to search"),
    limit: int = Query(5, ge=1, le=100, description="Max results")
) -> QueryResponse:
    """Simple search via query parameters."""
    request = QueryRequest(query=q, namespace=namespace, top_k=limit)
    return await query(request)
```

---

## 4. Chat/Ask Endpoint with SSE Streaming

### Create `backend/api/chat.py`

```python
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.models.requests import AskRequest
from backend.models.responses import AskResponse, SourceInfo, ProviderInfo, ProvidersResponse
from backend.graph.runner import run_rag_query, get_conversation_history, clear_conversation
from backend.config import settings
import json
import httpx

router = APIRouter()

async def ask(request: AskRequest):
    """
    Ask a question with RAG using LangGraph workflow.

    Supports conversation memory via thread_id.
    """
    if request.stream:
        return StreamingResponse(
            stream_response(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        result = await run_rag_query(
            question=request.question,
            namespace=request.namespace,
            provider=request.provider,
            model=request.model,
            thread_id=request.thread_id,
            stream=False
        )

        return AskResponse(
            answer=result["answer"],
            sources=[SourceInfo(**s) for s in result["sources"]],
            provider=request.provider,
            model=request.model or "default",
            thread_id=result["thread_id"],
            has_context=result["has_context"]
        )


async def stream_response(request: AskRequest):
    """Generate SSE stream using LangGraph."""
    try:
        stream = await run_rag_query(
            question=request.question,
            namespace=request.namespace,
            provider=request.provider,
            model=request.model,
            thread_id=request.thread_id,
            stream=True
        )

        async for event in stream:
            if event["type"] == "sources":
                yield f"data: {json.dumps({'sources': event['sources']})}\n\n"
            elif event["type"] == "token":
                yield f"data: {json.dumps({'token': event['token']})}\n\n"
            elif event["type"] == "done":
                yield f"data: {json.dumps({'thread_id': event['thread_id']})}\n\n"
                yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"


async def list_providers():
    """List available LLM providers and their status."""
    providers = []

    # OpenAI - always available if API key is set
    providers.append(ProviderInfo(
        name="openai",
        available=bool(settings.openai_api_key),
        models=["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
    ))

    # Anthropic
    providers.append(ProviderInfo(
        name="anthropic",
        available=bool(settings.anthropic_api_key),
        models=["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
    ))

    # Ollama - check if running
    ollama_available = False
    ollama_models = []
    ollama_error = None

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url}/api/tags")
            if response.status_code == 200:
                ollama_available = True
                data = response.json()
                ollama_models = [m["name"] for m in data.get("models", [])][:5]
    except Exception as e:
        ollama_error = str(e)

    providers.append(ProviderInfo(
        name="ollama",
        available=ollama_available,
        models=ollama_models or ["llama3", "mistral", "codellama"],
        error=ollama_error
    ))

    return ProvidersResponse(
        providers=providers,
        default={
            "provider": settings.default_llm_provider,
            "model": settings.default_llm_model or "default"
        }
    )


async def get_history(thread_id: str):
    """Get conversation history for a thread."""
    history = await get_conversation_history(thread_id)
    return {"thread_id": thread_id, "messages": history}


async def delete_history(thread_id: str):
    """Clear conversation history."""
    success = await clear_conversation(thread_id)
    if success:
        return {"status": "cleared", "thread_id": thread_id}
    raise HTTPException(404, "Thread not found")
```

---

## 5. Status Endpoint

### Create `backend/api/status.py`

```python
from backend.models.responses import StatusResponse, IndexStats
from backend.vectordb.pinecone import get_index_stats
from backend.config import settings

async def get_status() -> StatusResponse:
    """Get index statistics."""
    stats = await get_index_stats()

    return StatusResponse(
        status="healthy",
        index=IndexStats(
            name=settings.pinecone_index_name,
            total_vectors=stats.get("total_vector_count", 0),
            dimension=stats.get("dimension", settings.embedding_dimensions),
            namespaces=stats.get("namespaces", {})
        ),
        embedding_model=settings.embedding_model
    )
```

---

## 6. Jobs Endpoint

### Create `backend/api/jobs.py`

```python
from fastapi import HTTPException, Query
from typing import Optional
from backend.services.job_store import get_job, list_jobs
from backend.models.job import JobInfo, JobListResponse

async def get_job_status(job_id: str) -> JobInfo:
    """Get status of a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job

async def list_all_jobs(
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    limit: int = Query(50, ge=1, le=200, description="Max jobs to return")
) -> JobListResponse:
    """List recent jobs."""
    jobs = list_jobs(namespace=namespace, limit=limit)
    return JobListResponse(jobs=jobs, count=len(jobs))
```

---

## 7. Main Application

### Create `backend/main.py`

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.vectordb.pinecone import init_pinecone
from backend.api import routes
from backend.logging_config import setup_logging
from backend.config import settings
import redis
import logging

# Setup logging
setup_logging(level=settings.log_level)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("Starting LLM-MD Backend...")
    init_pinecone()
    logger.info("Pinecone initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="LLM-MD Backend",
    description="Backend for indexing and querying markdown files with LLMs",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(routes.router, prefix="/api")

@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check."""
    from backend.vectordb.pinecone import get_index_stats

    checks = {"api": "healthy", "redis": "unknown", "pinecone": "unknown"}

    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"

    # Check Pinecone
    try:
        stats = await get_index_stats()
        checks["pinecone"] = "healthy"
        checks["pinecone_vectors"] = stats.get("total_vector_count", 0)
    except Exception as e:
        checks["pinecone"] = f"unhealthy: {str(e)}"

    overall = "healthy" if all(
        v == "healthy" or isinstance(v, int)
        for v in checks.values()
    ) else "degraded"

    return {"status": overall, "checks": checks}
```

---

## Related Files

- [models.md](./models.md) - Pydantic models for requests/responses
- [backend-core.md](./backend-core.md) - Core backend modules
- [backend-services.md](./backend-services.md) - RAG, job store, webhook services
- [langgraph.md](./langgraph.md) - LangGraph workflow used by chat endpoint
