from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.heartbeat_job import HeartbeatJob
from backend.models.heartbeat_job_run import HeartbeatJobRun
from backend.schemas.heartbeat import (
    HeartbeatJobCreate,
    HeartbeatJobUpdate,
    HeartbeatJobToggle,
    HeartbeatJobResponse,
    HeartbeatJobRunResponse,
    HeartbeatJobRunListResponse,
    resolve_cron_expression,
)
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/heartbeat-jobs", tags=["heartbeat-jobs"])

_JOB_LIMIT = 20


def _compute_next_run(cron_expression: str) -> datetime:
    """Compute the next run time from a cron expression."""
    from croniter import croniter
    return croniter(cron_expression, datetime.utcnow()).get_next(datetime)


def _to_response(job: HeartbeatJob) -> HeartbeatJobResponse:
    return HeartbeatJobResponse(
        id=job.id,
        name=job.name,
        prompt=job.prompt,
        schedule_type=job.schedule_type,
        schedule_value=job.schedule_value,
        cron_expression=job.cron_expression,
        is_active=job.is_active,
        next_run_at=job.next_run_at,
        last_run_at=job.last_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=List[HeartbeatJobResponse])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all heartbeat jobs for the current user."""
    jobs = (
        db.query(HeartbeatJob)
        .filter(HeartbeatJob.user_id == current_user.id)
        .order_by(HeartbeatJob.created_at.desc())
        .all()
    )
    return [_to_response(j) for j in jobs]


@router.post("", response_model=HeartbeatJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: HeartbeatJobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new heartbeat job."""
    count = db.query(HeartbeatJob).filter(HeartbeatJob.user_id == current_user.id).count()
    if count >= _JOB_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum of {_JOB_LIMIT} jobs allowed per user",
        )

    cron_expression = resolve_cron_expression(request.schedule_type, request.schedule_value)
    next_run_at = _compute_next_run(cron_expression)

    job = HeartbeatJob(
        user_id=current_user.id,
        name=request.name,
        prompt=request.prompt,
        schedule_type=request.schedule_type,
        schedule_value=request.schedule_value,
        cron_expression=cron_expression,
        next_run_at=next_run_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_response(job)


@router.get("/{job_id}", response_model=HeartbeatJobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single heartbeat job."""
    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.id == job_id,
        HeartbeatJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.put("/{job_id}", response_model=HeartbeatJobResponse)
async def update_job(
    job_id: str,
    request: HeartbeatJobUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a heartbeat job."""
    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.id == job_id,
        HeartbeatJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if request.name is not None:
        job.name = request.name
    if request.prompt is not None:
        job.prompt = request.prompt

    schedule_type = request.schedule_type or job.schedule_type
    schedule_value = request.schedule_value or job.schedule_value
    if request.schedule_type is not None or request.schedule_value is not None:
        cron_expression = resolve_cron_expression(schedule_type, schedule_value)
        job.schedule_type = schedule_type
        job.schedule_value = schedule_value
        job.cron_expression = cron_expression
        job.next_run_at = _compute_next_run(cron_expression)

    db.commit()
    db.refresh(job)
    return _to_response(job)


@router.patch("/{job_id}", response_model=HeartbeatJobResponse)
async def toggle_job(
    job_id: str,
    request: HeartbeatJobToggle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a heartbeat job's active state."""
    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.id == job_id,
        HeartbeatJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.is_active = request.is_active
    # Recompute next_run_at when re-activating
    if request.is_active:
        job.next_run_at = _compute_next_run(job.cron_expression)
    db.commit()
    db.refresh(job)
    return _to_response(job)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a heartbeat job and all its runs."""
    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.id == job_id,
        HeartbeatJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()


@router.get("/{job_id}/runs", response_model=HeartbeatJobRunListResponse)
async def list_runs(
    job_id: str,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List run history for a heartbeat job, newest first."""
    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.id == job_id,
        HeartbeatJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    total = db.query(HeartbeatJobRun).filter(HeartbeatJobRun.job_id == job_id).count()
    runs = (
        db.query(HeartbeatJobRun)
        .filter(HeartbeatJobRun.job_id == job_id)
        .order_by(HeartbeatJobRun.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return HeartbeatJobRunListResponse(
        runs=[
            HeartbeatJobRunResponse(
                id=r.id,
                job_id=r.job_id,
                status=r.status,
                started_at=r.started_at,
                completed_at=r.completed_at,
                prompt=r.prompt,
                response=r.response,
                error=r.error,
                duration_ms=r.duration_ms,
            )
            for r in runs
        ],
        total=total,
    )


@router.post("/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a heartbeat job run."""
    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.id == job_id,
        HeartbeatJob.user_id == current_user.id,
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    from backend.tasks.heartbeat_tasks import execute_heartbeat_job
    task = execute_heartbeat_job.delay(job_id)
    return {"task_id": task.id, "job_id": job_id}
