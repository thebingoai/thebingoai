# Phase 4: Async Processing & Webhooks

## Overview
Implement background job processing with Redis + Celery for large uploads, and webhook notifications when jobs complete.

## Duration: Week 4 (Part 1)

---

## Task 4.1: Add Celery Dependencies

### Update `backend/requirements.txt`

```
# Existing dependencies...

# Async processing
celery[redis]==5.3.6
redis==5.0.1
```

---

## Task 4.2: Celery Configuration

### Create `backend/celery_app.py`

```python
from celery import Celery
from backend.config import settings

celery_app = Celery(
    "llm-md-backend",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["backend.tasks.upload_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minute timeout
    worker_prefetch_multiplier=1,  # Process one task at a time
)
```

### Update `backend/config.py`

```python
class Settings(BaseSettings):
    # Existing settings...

    # Redis/Celery settings
    redis_url: str = "redis://localhost:6379/0"

    # Async processing thresholds
    async_file_size_threshold: int = 100_000  # 100KB
    async_chunk_count_threshold: int = 20

    class Config:
        env_file = ".env"
```

### Update `.env.example`

```
# Existing vars...

# Redis
REDIS_URL=redis://localhost:6379/0

# Async thresholds
ASYNC_FILE_SIZE_THRESHOLD=100000
ASYNC_CHUNK_COUNT_THRESHOLD=20
```

---

## Task 4.3: Job Status Model

### Create `backend/models/job.py`

```python
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    file_name: str
    namespace: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: int = 0  # 0-100
    chunks_total: int | None = None
    chunks_processed: int | None = None
    error: str | None = None
    result: dict | None = None
```

---

## Task 4.4: Redis Job Storage

### Create `backend/services/job_store.py`

```python
import json
import redis
from datetime import datetime
from backend.config import settings
from backend.models.job import JobInfo, JobStatus

redis_client = redis.from_url(settings.redis_url)

JOB_PREFIX = "job:"
JOB_TTL = 86400 * 7  # 7 days

def create_job(
    job_id: str,
    file_name: str,
    namespace: str
) -> JobInfo:
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

def get_job(job_id: str) -> JobInfo | None:
    """Get job by ID."""
    data = redis_client.get(f"{JOB_PREFIX}{job_id}")
    if data:
        return JobInfo.model_validate_json(data)
    return None

def update_job(job_id: str, **updates) -> JobInfo | None:
    """Update job fields."""
    job = get_job(job_id)
    if not job:
        return None

    job_dict = job.model_dump()
    job_dict.update(updates)
    updated_job = JobInfo(**job_dict)

    redis_client.setex(
        f"{JOB_PREFIX}{job_id}",
        JOB_TTL,
        updated_job.model_dump_json()
    )
    return updated_job

def list_jobs(namespace: str | None = None, limit: int = 50) -> list[JobInfo]:
    """List recent jobs, optionally filtered by namespace."""
    jobs = []
    for key in redis_client.scan_iter(f"{JOB_PREFIX}*"):
        data = redis_client.get(key)
        if data:
            job = JobInfo.model_validate_json(data)
            if namespace is None or job.namespace == namespace:
                jobs.append(job)
            if len(jobs) >= limit:
                break
    return sorted(jobs, key=lambda j: j.created_at, reverse=True)
```

---

## Task 4.5: Celery Upload Task

### Create `backend/tasks/__init__.py`

### Create `backend/tasks/upload_tasks.py`

```python
import uuid
from datetime import datetime
from celery import current_task
from backend.celery_app import celery_app
from backend.services.job_store import update_job, get_job
from backend.models.job import JobStatus
from backend.parser.markdown import chunk_markdown
from backend.embedder.openai import embed_batch
from backend.vectordb.pinecone import upsert_vectors
from backend.services.webhook import send_webhook

@celery_app.task(bind=True)
def process_upload_async(
    self,
    job_id: str,
    file_content: str,
    file_name: str,
    namespace: str,
    tags: list[str],
    webhook_url: str | None
):
    """
    Process file upload asynchronously.

    Args:
        job_id: Unique job identifier
        file_content: Raw markdown content
        file_name: Original filename
        namespace: Target namespace
        tags: File tags
        webhook_url: Optional webhook for completion notification
    """
    try:
        # Update status to processing
        update_job(
            job_id,
            status=JobStatus.PROCESSING,
            started_at=datetime.utcnow()
        )

        # 1. Chunk the markdown
        chunks = chunk_markdown(file_content)
        total_chunks = len(chunks)

        update_job(job_id, chunks_total=total_chunks)

        # 2. Generate embeddings in batches
        chunk_texts = [c["text"] for c in chunks]
        embeddings = []

        batch_size = 50
        for i in range(0, len(chunk_texts), batch_size):
            batch = chunk_texts[i:i + batch_size]
            batch_embeddings = embed_batch(batch)  # sync call
            embeddings.extend(batch_embeddings)

            # Update progress
            progress = int((i + len(batch)) / total_chunks * 80)  # 0-80%
            update_job(job_id, progress=progress, chunks_processed=i + len(batch))

        # 3. Prepare vectors for upsert
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
        update_job(job_id, progress=85)
        upsert_result = upsert_vectors(vectors, namespace)  # sync call

        # 5. Mark complete
        result = {
            "file_name": file_name,
            "chunks_created": total_chunks,
            "vectors_upserted": upsert_result.get("upserted_count", total_chunks),
            "namespace": namespace
        }

        update_job(
            job_id,
            status=JobStatus.COMPLETED,
            completed_at=datetime.utcnow(),
            progress=100,
            result=result
        )

        # 6. Send webhook notification
        if webhook_url:
            send_webhook(webhook_url, job_id, "completed", result)

        return result

    except Exception as e:
        update_job(
            job_id,
            status=JobStatus.FAILED,
            error=str(e),
            completed_at=datetime.utcnow()
        )

        if webhook_url:
            send_webhook(webhook_url, job_id, "failed", {"error": str(e)})

        raise
```

---

## Task 4.6: Webhook Service

### Create `backend/services/webhook.py`

```python
import httpx
from datetime import datetime

def send_webhook(
    webhook_url: str,
    job_id: str,
    status: str,
    data: dict
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
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            return response.status_code < 400
    except Exception as e:
        # Log but don't fail the job
        print(f"Webhook delivery failed: {e}")
        return False
```

---

## Task 4.7: Update Upload Endpoint

### Update `backend/api/upload.py`

```python
import uuid
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks
from backend.config import settings
from backend.parser.markdown import chunk_markdown, count_tokens
from backend.services.job_store import create_job, get_job
from backend.tasks.upload_tasks import process_upload_async

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    namespace: str = Form("default"),
    tags: str = Form(""),
    webhook_url: str | None = Form(None),
    force_async: bool = Form(False)
):
    """
    Upload and index a markdown file.

    Small files are processed synchronously.
    Large files are queued for async processing.

    Args:
        file: Markdown file
        namespace: Target namespace
        tags: Comma-separated tags
        webhook_url: URL for completion notification (async only)
        force_async: Force async processing regardless of size
    """
    # Validate file type
    if not file.filename.endswith(".md"):
        raise HTTPException(400, "Only .md files are supported")

    content = await file.read()
    content_str = content.decode("utf-8")
    file_size = len(content)

    tags_list = [t.strip() for t in tags.split(",") if t.strip()]

    # Determine if async processing is needed
    should_async = (
        force_async or
        file_size > settings.async_file_size_threshold
    )

    # Quick check: estimate chunks
    if not should_async:
        estimated_tokens = count_tokens(content_str)
        estimated_chunks = estimated_tokens // (settings.chunk_size * 0.8)
        if estimated_chunks > settings.async_chunk_count_threshold:
            should_async = True

    if should_async:
        # Async processing
        job_id = str(uuid.uuid4())
        job = create_job(job_id, file.filename, namespace)

        # Queue the task
        process_upload_async.delay(
            job_id=job_id,
            file_content=content_str,
            file_name=file.filename,
            namespace=namespace,
            tags=tags_list,
            webhook_url=webhook_url
        )

        return {
            "status": "queued",
            "job_id": job_id,
            "message": "File queued for processing",
            "webhook_url": webhook_url
        }
    else:
        # Sync processing (existing logic)
        # ... process immediately and return result
        pass
```

---

## Task 4.8: Job Status Endpoint

### Create `backend/api/jobs.py`

```python
from fastapi import APIRouter, HTTPException
from backend.services.job_store import get_job, list_jobs

router = APIRouter()

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job

@router.get("/jobs")
async def list_all_jobs(
    namespace: str | None = None,
    limit: int = 50
):
    """List recent jobs."""
    jobs = list_jobs(namespace=namespace, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}
```

---

## Task 4.9: CLI Webhook Configuration

### Update `cli/cmd/config.py`

**Config file structure:**
```yaml
backend_url: http://localhost:8000
webhook_url: https://my-server.com/webhooks/mdcli
```

**Commands:**
```bash
mdcli config set-webhook <url>
mdcli config show
```

---

## Task 4.10: CLI Job Status Commands

### Create `cli/cmd/jobs.py`

**Commands:**

```bash
# Check specific job status
mdcli jobs status <job-id>

# List recent jobs
mdcli jobs list
mdcli jobs list --namespace=personal

# Wait for job completion
mdcli jobs wait <job-id>
mdcli jobs wait <job-id> --timeout=300
```

**Output (status):**

```
Job: 550e8400-e29b-41d4-a716-446655440000
Status: processing
File: large-notes.md
Namespace: personal
Progress: 65% (32/50 chunks)
Started: 2024-01-15 10:30:00 UTC
```

**Output (completed):**

```
Job: 550e8400-e29b-41d4-a716-446655440000
Status: ✓ completed
File: large-notes.md
Namespace: personal

Result:
  Chunks created: 50
  Vectors upserted: 50
  Completed: 2024-01-15 10:32:15 UTC
```

---

## Task 4.11: Update Upload Command

### Update `cli/cmd/upload.py`

```bash
# Upload with webhook notification
mdcli upload ./large-doc.md --webhook

# Force async processing
mdcli upload ./doc.md --async

# Show job ID for async uploads
# Output:
# ⏳ File queued for processing
# Job ID: 550e8400-e29b-41d4-a716-446655440000
# Check status with: mdcli jobs status 550e8400-e29b-41d4-a716-446655440000
```

---

## Task 4.12: Update API Router

### Update `backend/api/routes.py`

```python
from backend.api import upload, query, status, chat, jobs

router = APIRouter()

# Existing routes...

# Job routes
router.get("/jobs")(jobs.list_all_jobs)
router.get("/jobs/{job_id}")(jobs.get_job_status)
```

---

## Verification Checklist

After implementation, verify:

- [ ] Redis is running and accessible
- [ ] Celery worker starts: `celery -A backend.celery_app worker --loglevel=info`
- [ ] Small files still process synchronously
- [ ] Large files get queued (check with `--force-async`)
- [ ] Job status updates correctly (pending → processing → completed)
- [ ] Progress percentage updates during processing
- [ ] Webhook is called on completion
- [ ] Webhook is called on failure
- [ ] CLI can check job status
- [ ] CLI can list recent jobs
- [ ] CLI wait command works

---

## Testing Commands

```bash
# Start Redis (if not using Docker yet)
redis-server

# Start Celery worker
celery -A backend.celery_app worker --loglevel=info

# Start FastAPI (separate terminal)
uvicorn backend.main:app --reload

# Test sync upload (small file)
curl -X POST http://localhost:8000/api/upload \
  -F "file=@small.md" \
  -F "namespace=test"

# Test async upload (force)
curl -X POST http://localhost:8000/api/upload \
  -F "file=@large.md" \
  -F "namespace=test" \
  -F "force_async=true" \
  -F "webhook_url=https://webhook.site/your-id"

# Check job status
curl http://localhost:8000/api/jobs/<job-id>

# List jobs
curl http://localhost:8000/api/jobs

# CLI commands
python -m cli.main upload ./large.md --async
python -m cli.main jobs status <job-id>
python -m cli.main jobs list
python -m cli.main jobs wait <job-id>
```
