"""API endpoints for dashboard schedule management."""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.dashboard import Dashboard
from backend.models.dashboard_refresh_run import DashboardRefreshRun
from backend.schemas.dashboard_schedule import (
    DashboardScheduleUpdate,
    DashboardScheduleToggle,
    DashboardScheduleResponse,
    DashboardRefreshRunResponse,
    DashboardRefreshRunListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboard-schedule"])


def _get_dashboard_or_404(dashboard_id: int, user_id: str, db: Session) -> Dashboard:
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == user_id,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dashboard


@router.put("/{dashboard_id}/schedule", response_model=DashboardScheduleResponse)
async def set_schedule(
    dashboard_id: int,
    payload: DashboardScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or update the refresh schedule for a dashboard."""
    from croniter import croniter
    from backend.schemas.heartbeat import resolve_cron_expression

    dashboard = _get_dashboard_or_404(dashboard_id, current_user.id, db)

    try:
        cron_expr = resolve_cron_expression(payload.schedule_type, payload.schedule_value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = datetime.utcnow()
    dashboard.schedule_type = payload.schedule_type
    dashboard.schedule_value = payload.schedule_value
    dashboard.cron_expression = cron_expr
    dashboard.schedule_active = True
    dashboard.next_run_at = croniter(cron_expr, now).get_next(datetime)

    db.commit()
    db.refresh(dashboard)
    return DashboardScheduleResponse.model_validate(dashboard)


@router.patch("/{dashboard_id}/schedule", response_model=DashboardScheduleResponse)
async def toggle_schedule(
    dashboard_id: int,
    payload: DashboardScheduleToggle,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle the active/inactive state of a dashboard schedule."""
    from croniter import croniter

    dashboard = _get_dashboard_or_404(dashboard_id, current_user.id, db)

    if not dashboard.cron_expression:
        raise HTTPException(status_code=400, detail="Dashboard has no schedule configured")

    dashboard.schedule_active = payload.schedule_active

    # Recompute next_run_at when reactivating
    if payload.schedule_active:
        now = datetime.utcnow()
        dashboard.next_run_at = croniter(dashboard.cron_expression, now).get_next(datetime)

    db.commit()
    db.refresh(dashboard)
    return DashboardScheduleResponse.model_validate(dashboard)


@router.delete("/{dashboard_id}/schedule", status_code=204)
async def remove_schedule(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the refresh schedule from a dashboard."""
    dashboard = _get_dashboard_or_404(dashboard_id, current_user.id, db)

    dashboard.schedule_type = None
    dashboard.schedule_value = None
    dashboard.cron_expression = None
    dashboard.schedule_active = False
    dashboard.next_run_at = None

    db.commit()


@router.get("/{dashboard_id}/schedule/runs", response_model=DashboardRefreshRunListResponse)
async def list_refresh_runs(
    dashboard_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List run history for a dashboard schedule."""
    _get_dashboard_or_404(dashboard_id, current_user.id, db)

    total = db.query(DashboardRefreshRun).filter(
        DashboardRefreshRun.dashboard_id == dashboard_id
    ).count()

    runs = (
        db.query(DashboardRefreshRun)
        .filter(DashboardRefreshRun.dashboard_id == dashboard_id)
        .order_by(DashboardRefreshRun.started_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    return DashboardRefreshRunListResponse(
        runs=[DashboardRefreshRunResponse.model_validate(r) for r in runs],
        total=total,
    )


@router.post("/{dashboard_id}/schedule/run", status_code=202)
async def trigger_refresh(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger a dashboard refresh (dispatches Celery task)."""
    from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh

    _get_dashboard_or_404(dashboard_id, current_user.id, db)
    execute_dashboard_refresh.delay(dashboard_id)

    return {"queued": True, "dashboard_id": dashboard_id}


_ANALYSIS_JOB_PREFIX = "Dashboard Analysis: "


@router.post("/{dashboard_id}/analysis-schedule", status_code=201)
async def set_analysis_schedule(
    dashboard_id: int,
    payload: DashboardScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update a recurring AI analysis job for a dashboard.

    On each firing the orchestrator agent analyzes the dashboard and delivers
    a narrative summary to the user's chat via the HeartbeatJob mechanism.
    """
    from croniter import croniter
    from backend.schemas.heartbeat import resolve_cron_expression
    from backend.models.heartbeat_job import HeartbeatJob

    dashboard = _get_dashboard_or_404(dashboard_id, current_user.id, db)

    try:
        cron_expr = resolve_cron_expression(payload.schedule_type, payload.schedule_value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_name = f"{_ANALYSIS_JOB_PREFIX}{dashboard.title}"
    now = datetime.utcnow()
    next_run = croniter(cron_expr, now).get_next(datetime)

    existing = db.query(HeartbeatJob).filter(
        HeartbeatJob.user_id == current_user.id,
        HeartbeatJob.name == job_name,
    ).first()

    if existing:
        existing.schedule_type = payload.schedule_type
        existing.schedule_value = payload.schedule_value
        existing.cron_expression = cron_expr
        existing.next_run_at = next_run
        existing.is_active = True
        job = existing
    else:
        job = HeartbeatJob(
            user_id=current_user.id,
            name=job_name,
            prompt=(
                f"analyze dashboard {dashboard_id} and give me a summary of key metrics and trends"
            ),
            schedule_type=payload.schedule_type,
            schedule_value=payload.schedule_value,
            cron_expression=cron_expr,
            agent_type=None,  # orchestrator (default)
            is_active=True,
            next_run_at=next_run,
        )
        db.add(job)

    db.commit()
    db.refresh(job)

    return {
        "dashboard_id": dashboard_id,
        "job_id": job.id,
        "name": job.name,
        "schedule_type": job.schedule_type,
        "schedule_value": job.schedule_value,
        "next_run_at": job.next_run_at.isoformat() if job.next_run_at else None,
        "is_active": job.is_active,
    }


@router.delete("/{dashboard_id}/analysis-schedule", status_code=204)
async def remove_analysis_schedule(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove the recurring AI analysis job for a dashboard."""
    from backend.models.heartbeat_job import HeartbeatJob

    dashboard = _get_dashboard_or_404(dashboard_id, current_user.id, db)
    job_name = f"{_ANALYSIS_JOB_PREFIX}{dashboard.title}"

    job = db.query(HeartbeatJob).filter(
        HeartbeatJob.user_id == current_user.id,
        HeartbeatJob.name == job_name,
    ).first()

    if job:
        db.delete(job)
        db.commit()
