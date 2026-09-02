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
    dashboard_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List briefings for the current user, newest first. Optionally scope to one dashboard."""
    query = db.query(Briefing).filter(Briefing.user_id == current_user.id)
    if dashboard_id is not None:
        query = query.filter(Briefing.dashboard_id == dashboard_id)
    briefings = query.order_by(Briefing.created_at.desc()).limit(limit).all()
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

    # Manual briefings are async (202 + poll), so the worker-side charge can't
    # surface a sync error. Pre-check credits here and refuse with 402 when out.
    # No credit is recorded here — the real charge happens in briefing_runner.
    _InsufficientCreditsError = None
    try:
        from backend.plugins.loader import get_loaded_plugins
        if "bingo-admin" in get_loaded_plugins():
            from bingo_admin.credit_context import (
                CreditContextManager,
                InsufficientCreditsError as _InsufficientCreditsError,
            )
        else:
            from backend.services.token_tracking_service import (
                CreditContextManager,
                InsufficientCreditsError as _InsufficientCreditsError,
            )
        _credit_mgr = CreditContextManager(
            db=db,
            user_id=current_user.id,
            title="Briefing",
            provider_name=None,
            conversation_id=None,
            block_on_insufficient=True,
        )
        await _credit_mgr.__aenter__()  # check only; never __aexit__ → no record
    except Exception as _credit_err:
        if _InsufficientCreditsError is not None and isinstance(_credit_err, _InsufficientCreditsError):
            cap = getattr(_credit_err, "reason", "user_daily")
            raise HTTPException(
                status_code=402,
                detail={
                    "error_code": "insufficient_credits",
                    "cap": cap,
                    "message": (
                        "Workspace credit pool exhausted."
                        if cap == "org_pool"
                        else "Daily credits used up."
                    ),
                },
            )
        # Pre-check failed for a non-credit reason — roll back any aborted
        # transaction so the request session stays usable, then proceed
        # (credit wiring must never block a briefing).
        db.rollback()
        logger.warning("Briefing credit pre-check setup failed: %s", _credit_err)

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
    # Read scope must match GET /dashboards/{id} — a chat chart embed points at a
    # dashboard the user reached through the org-wide list, so owner-only here
    # 404s the embed for every non-owner who can legitimately read it.
    from backend.api.dashboards import _dashboard_visible_to

    dashboard = _dashboard_visible_to(
        db.query(Dashboard).filter(Dashboard.id == dashboard_id), current_user, db,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    widgets = dashboard.widgets or []
    for w in widgets:
        if w.get("id") == widget_id:
            return w
    raise HTTPException(status_code=404, detail="Widget not found")
