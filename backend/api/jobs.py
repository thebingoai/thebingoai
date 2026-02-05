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
