# Backend Services

Complete implementations for RAG service, job store, and webhook notification service.

---

## 1. RAG Service (Simple Version)

This is a standalone RAG service that can be used without LangGraph. For the LangGraph-based implementation with conversation memory, see [langgraph.md](./langgraph.md).

### Create `backend/services/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/services/rag.py`

```python
from typing import Optional, AsyncGenerator, Union
from backend.vectordb.pinecone import query_vectors
from backend.embedder.openai import embed_text
from backend.llm.factory import get_provider
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the user's personal notes and documents.

Use the provided context to answer the question. If the context contains relevant information, cite it specifically. If the context doesn't contain enough information to fully answer the question, say so clearly and provide what help you can based on what is available.

Be concise but thorough. Use the same terminology found in the user's notes when possible.

Context from user's documents:
---
{context}
---

Remember: Only use information from the context above. If you're not sure about something, say so."""

async def ask_with_context(
    question: str,
    namespace: str = "default",
    top_k: int = 5,
    provider: str = "openai",
    model: Optional[str] = None,
    temperature: float = 0.7,
    stream: bool = False
) -> Union[dict, tuple[AsyncGenerator[str, None], list[dict]]]:
    """
    RAG: Retrieve relevant context and generate answer.

    Args:
        question: User's question
        namespace: Namespace to search
        top_k: Number of context chunks to retrieve
        provider: LLM provider to use
        model: Optional model override
        temperature: Generation temperature
        stream: Whether to stream response

    Returns:
        If stream=False: {"answer": str, "sources": list}
        If stream=True: (AsyncGenerator, sources)
    """
    logger.info(f"RAG query: {question[:50]}... (namespace={namespace}, provider={provider})")

    # 1. Embed the question
    query_embedding = await embed_text(question)

    # 2. Retrieve relevant chunks
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=top_k
    )

    if not results:
        logger.warning(f"No results found for query in namespace {namespace}")

    # 3. Build context from results
    context_parts = []
    sources = []

    for r in results:
        source = r["metadata"].get("source", "unknown")
        chunk_idx = r["metadata"].get("chunk_index", 0)
        text = r["metadata"].get("text", "")

        context_parts.append(f"[Source: {source}, Section {chunk_idx}]\n{text}")
        sources.append({
            "source": source,
            "chunk_index": chunk_idx,
            "score": round(r["score"], 4)
        })

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # 4. Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": question}
    ]

    # 5. Get LLM response
    llm = get_provider(provider, model)

    if stream:
        async def stream_with_context():
            async for token in llm.chat_stream(messages, temperature=temperature):
                yield token

        return stream_with_context(), sources
    else:
        answer = await llm.chat(messages, temperature=temperature)
        return {"answer": answer, "sources": sources}


async def get_context_only(
    question: str,
    namespace: str = "default",
    top_k: int = 5
) -> list[dict]:
    """
    Retrieve context without generating an answer.
    Useful for debugging or when client wants to handle LLM separately.
    """
    query_embedding = await embed_text(question)

    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=top_k
    )

    return [
        {
            "source": r["metadata"].get("source", "unknown"),
            "chunk_index": r["metadata"].get("chunk_index", 0),
            "text": r["metadata"].get("text", ""),
            "score": round(r["score"], 4)
        }
        for r in results
    ]
```

---

## 2. Job Store Service

Redis-backed job storage for async task tracking.

### Create `backend/services/job_store.py`

```python
import json
import redis
from datetime import datetime
from typing import Optional
from backend.config import settings
from backend.models.job import JobInfo, JobStatus, JobResult

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

JOB_PREFIX = "job:"
JOB_TTL = 86400 * 7  # 7 days

def create_job(job_id: str, file_name: str, namespace: str) -> JobInfo:
    """Create a new job record."""
    job = JobInfo(
        job_id=job_id,
        status=JobStatus.PENDING,
        file_name=file_name,
        namespace=namespace,
        created_at=datetime.utcnow()
    )
    redis_client.setex(
        f"{JOB_PREFIX}{job_id}",
        JOB_TTL,
        job.model_dump_json()
    )
    return job

def get_job(job_id: str) -> Optional[JobInfo]:
    """Get job by ID."""
    data = redis_client.get(f"{JOB_PREFIX}{job_id}")
    if data:
        return JobInfo.model_validate_json(data)
    return None

def update_job(job_id: str, **updates) -> Optional[JobInfo]:
    """Update job fields."""
    job = get_job(job_id)
    if not job:
        return None

    job_dict = job.model_dump()
    job_dict.update(updates)

    # Handle nested result dict
    if "result" in updates and isinstance(updates["result"], dict):
        job_dict["result"] = JobResult(**updates["result"])

    updated_job = JobInfo(**job_dict)

    redis_client.setex(
        f"{JOB_PREFIX}{job_id}",
        JOB_TTL,
        updated_job.model_dump_json()
    )
    return updated_job

def start_job(job_id: str, chunks_total: int = None) -> Optional[JobInfo]:
    """Mark job as processing."""
    updates = {
        "status": JobStatus.PROCESSING,
        "started_at": datetime.utcnow(),
        "progress": 0
    }
    if chunks_total:
        updates["chunks_total"] = chunks_total
    return update_job(job_id, **updates)

def update_progress(job_id: str, chunks_processed: int, progress: int) -> Optional[JobInfo]:
    """Update job progress."""
    return update_job(
        job_id,
        chunks_processed=chunks_processed,
        progress=progress
    )

def complete_job(
    job_id: str,
    file_name: str,
    chunks_created: int,
    vectors_upserted: int,
    namespace: str
) -> Optional[JobInfo]:
    """Mark job as completed."""
    return update_job(
        job_id,
        status=JobStatus.COMPLETED,
        completed_at=datetime.utcnow(),
        progress=100,
        result={
            "file_name": file_name,
            "chunks_created": chunks_created,
            "vectors_upserted": vectors_upserted,
            "namespace": namespace
        }
    )

def fail_job(job_id: str, error: str) -> Optional[JobInfo]:
    """Mark job as failed."""
    return update_job(
        job_id,
        status=JobStatus.FAILED,
        completed_at=datetime.utcnow(),
        error=error
    )

def list_jobs(namespace: Optional[str] = None, limit: int = 50) -> list[JobInfo]:
    """List recent jobs, optionally filtered by namespace."""
    jobs = []
    cursor = 0

    while True:
        cursor, keys = redis_client.scan(cursor, match=f"{JOB_PREFIX}*", count=100)

        for key in keys:
            data = redis_client.get(key)
            if data:
                try:
                    job = JobInfo.model_validate_json(data)
                    if namespace is None or job.namespace == namespace:
                        jobs.append(job)
                except Exception:
                    continue

            if len(jobs) >= limit * 2:  # Get extra for sorting
                break

        if cursor == 0 or len(jobs) >= limit * 2:
            break

    # Sort by created_at descending and limit
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs[:limit]

def delete_job(job_id: str) -> bool:
    """Delete a job record."""
    return redis_client.delete(f"{JOB_PREFIX}{job_id}") > 0
```

---

## 3. Webhook Service

Send webhook notifications for async job completion.

### Create `backend/services/webhook.py`

```python
import httpx
from datetime import datetime
from typing import Any
import logging

logger = logging.getLogger(__name__)

async def send_webhook(
    webhook_url: str,
    job_id: str,
    status: str,
    data: dict[str, Any]
) -> bool:
    """
    Send webhook notification.

    Payload format:
    {
        "event": "upload.completed" | "upload.failed",
        "job_id": "...",
        "timestamp": "2024-01-15T10:30:00Z",
        "data": {...}
    }
    """
    payload = {
        "event": f"upload.{status}",
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "mdcli-backend/0.1.0"
                }
            )
            success = response.status_code < 400

            if success:
                logger.info(f"Webhook delivered to {webhook_url}")
            else:
                logger.warning(f"Webhook failed: {response.status_code} - {response.text[:100]}")

            return success

    except httpx.TimeoutException:
        logger.error(f"Webhook timeout: {webhook_url}")
        return False
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return False

# Sync version for Celery tasks
def send_webhook_sync(
    webhook_url: str,
    job_id: str,
    status: str,
    data: dict[str, Any]
) -> bool:
    """Synchronous webhook sender for Celery tasks."""
    import asyncio
    return asyncio.run(send_webhook(webhook_url, job_id, status, data))
```

---

## 4. Celery Tasks

Background tasks for async processing.

### Create `backend/tasks/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/celery_app.py`

```python
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "llm-md-backend",
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    task_soft_time_limit=540,  # 9 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["backend.tasks"])
```

### Create `backend/tasks/upload_tasks.py`

```python
from datetime import datetime
from backend.celery_app import celery_app
from backend.config import settings
from backend.parser.markdown import chunk_markdown
from backend.embedder.openai import embed_batch_sync
from backend.vectordb.pinecone import upsert_vectors_sync
from backend.services.job_store import start_job, update_progress, complete_job, fail_job
from backend.services.webhook import send_webhook_sync
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def process_upload_async(
    self,
    job_id: str,
    file_content: str,
    file_name: str,
    namespace: str,
    tags: list[str],
    webhook_url: str = None
):
    """
    Process file upload asynchronously.

    Called by Celery worker.
    """
    try:
        logger.info(f"Starting async upload: job={job_id}, file={file_name}")

        # 1. Chunk the content
        chunks = chunk_markdown(
            file_content,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap
        )

        if not chunks:
            fail_job(job_id, "No content to index")
            return {"status": "failed", "error": "No content to index"}

        # Mark job as started
        start_job(job_id, chunks_total=len(chunks))

        # 2. Embed in batches
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embed_batch_sync(chunk_texts, batch_size=50)

        # Update progress (50%)
        update_progress(job_id, chunks_processed=len(chunks), progress=50)

        # 3. Prepare vectors
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors.append({
                "id": f"{file_name}#chunk-{i}",
                "values": embedding,
                "metadata": {
                    "source": file_name,
                    "chunk_index": i,
                    "text": chunk["text"],
                    "tags": tags,
                    "created_at": datetime.utcnow().isoformat()
                }
            })

        # 4. Upsert to Pinecone
        result = upsert_vectors_sync(vectors, namespace)

        # 5. Mark complete
        complete_job(
            job_id=job_id,
            file_name=file_name,
            chunks_created=len(chunks),
            vectors_upserted=result.get("upserted_count", len(chunks)),
            namespace=namespace
        )

        logger.info(f"Completed async upload: job={job_id}, chunks={len(chunks)}")

        # 6. Send webhook if configured
        if webhook_url:
            send_webhook_sync(
                webhook_url=webhook_url,
                job_id=job_id,
                status="completed",
                data={
                    "file_name": file_name,
                    "chunks_created": len(chunks),
                    "vectors_upserted": result.get("upserted_count", len(chunks)),
                    "namespace": namespace
                }
            )

        return {
            "status": "completed",
            "job_id": job_id,
            "chunks_created": len(chunks)
        }

    except Exception as e:
        logger.error(f"Async upload failed: job={job_id}, error={e}")
        fail_job(job_id, str(e))

        # Send failure webhook
        if webhook_url:
            send_webhook_sync(
                webhook_url=webhook_url,
                job_id=job_id,
                status="failed",
                data={"error": str(e)}
            )

        # Retry if appropriate
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

        return {"status": "failed", "job_id": job_id, "error": str(e)}
```

---

## Related Files

- [models.md](./models.md) - JobInfo, JobStatus models
- [backend-core.md](./backend-core.md) - Embedder, Pinecone used by tasks
- [backend-api.md](./backend-api.md) - API endpoints for jobs
- [langgraph.md](./langgraph.md) - LangGraph-based RAG with conversation memory
- [phase-4-async-webhooks.md](./phase-4-async-webhooks.md) - Async processing phase
