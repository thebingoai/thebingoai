import json
import redis
from datetime import datetime
from typing import Optional
from backend.config import settings
from backend.models.job import JobInfo, JobStatus, JobResult

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

JOB_PREFIX = "job:"

def create_job(job_id: str, file_name: str, namespace: str) -> JobInfo:
    """Create a new job record."""
    job = JobInfo(
        job_id=job_id,
        status=JobStatus.PENDING,
        file_name=file_name,
        namespace=namespace,
        created_at=datetime.now(datetime.UTC)
    )
    redis_client.setex(
        f"{JOB_PREFIX}{job_id}",
        settings.job_ttl_seconds,
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
        settings.job_ttl_seconds,
        updated_job.model_dump_json()
    )
    return updated_job

def start_job(job_id: str, chunks_total: int = None) -> Optional[JobInfo]:
    """Mark job as processing."""
    updates = {
        "status": JobStatus.PROCESSING,
        "started_at": datetime.now(datetime.UTC),
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
        completed_at=datetime.now(datetime.UTC),
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
        completed_at=datetime.now(datetime.UTC),
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
