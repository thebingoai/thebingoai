"""Briefings API — POST /dashboards/{id}/brief, GET /briefings/{id}."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.dashboard import Dashboard
from backend.models.briefing import Briefing
from backend.schemas.briefing import BriefingResponse
from backend.tasks.briefing_tasks import generate_briefing

logger = logging.getLogger(__name__)

router = APIRouter(tags=["briefings"])


def _with_dashboard_name(briefing: Briefing, db: Session) -> BriefingResponse:
    dashboard = db.query(Dashboard).filter(Dashboard.id == briefing.dashboard_id).first()
    data = BriefingResponse.model_validate(briefing)
    data.dashboard_name = dashboard.title if dashboard else None
    return data


@router.get("/briefings", response_model=list[BriefingResponse])
async def list_briefings(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List briefings for the current user, newest first."""
    briefings = (
        db.query(Briefing)
        .filter(Briefing.user_id == current_user.id)
        .order_by(Briefing.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_with_dashboard_name(b, db) for b in briefings]


@router.post("/dashboards/{dashboard_id}/brief", status_code=202)
async def create_briefing(
    dashboard_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new briefing for the dashboard. Returns 202 + briefing_id immediately;
    Celery task generates asynchronously. If a briefing is already in flight for this
    dashboard, returns the existing briefing_id."""
    dashboard = (
        db.query(Dashboard)
        .filter(Dashboard.id == dashboard_id, Dashboard.user_id == current_user.id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    existing = (
        db.query(Briefing)
        .filter(
            Briefing.user_id == current_user.id,
            Briefing.dashboard_id == dashboard_id,
            Briefing.status == "generating",
        )
        .first()
    )
    if existing:
        return {"briefing_id": existing.id, "status": "generating"}

    briefing = Briefing(
        user_id=current_user.id,
        dashboard_id=dashboard_id,
        source="manual",
        status="generating",
    )
    db.add(briefing)
    try:
        db.commit()
        db.refresh(briefing)
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(Briefing)
            .filter(
                Briefing.user_id == current_user.id,
                Briefing.dashboard_id == dashboard_id,
                Briefing.status == "generating",
            )
            .first()
        )
        if existing:
            return {"briefing_id": existing.id, "status": "generating"}
        raise HTTPException(status_code=500, detail="Failed to create briefing")

    generate_briefing.delay(briefing.id)
    return {"briefing_id": briefing.id, "status": "generating"}


@router.get("/briefings/{briefing_id}", response_model=BriefingResponse)
async def get_briefing(
    briefing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    briefing = db.query(Briefing).filter(
        Briefing.id == briefing_id,
        Briefing.user_id == current_user.id,
    ).first()
    if not briefing:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return _with_dashboard_name(briefing, db)


@router.get("/dashboards/{dashboard_id}/widgets/{widget_id}")
async def get_dashboard_widget(
    dashboard_id: int,
    widget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a single widget by its string id for embedding in a briefing."""
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    widgets = dashboard.widgets or []
    for w in widgets:
        if w.get("id") == widget_id:
            return w
    raise HTTPException(status_code=404, detail="Widget not found")
