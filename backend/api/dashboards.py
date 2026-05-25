import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.dashboard import Dashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


class DashboardCreate(BaseModel):
    title: str
    description: Optional[str] = None
    widgets: List[Any] = []


class DashboardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    widgets: Optional[List[Any]] = None


class DashboardResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    widgets: List[Any]
    data_context: Optional[Any] = None
    created_at: str
    updated_at: str
    schedule_type: Optional[str] = None
    schedule_value: Optional[str] = None
    cron_expression: Optional[str] = None
    schedule_active: bool = False
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None


def _dashboard_visible_to(query, current_user: User):
    """Phase 3 collaborative-workspace scope filter for dashboards.

    Same-org rows are visible; row whose owner currently lives in the caller's
    org are also visible (covers pre-Phase-0 rows that never got `org_id`
    backfilled). Falls back to owner-only when the caller has no org.
    """
    from sqlalchemy import or_

    if current_user.org_id is None:
        return query.filter(Dashboard.user_id == current_user.id)
    return query.outerjoin(User, Dashboard.user_id == User.id).filter(
        or_(
            Dashboard.org_id == current_user.org_id,
            User.org_id == current_user.org_id,
        )
    )


def _governance_require_mutate_dashboard(current_user: User, dashboard: Dashboard) -> None:
    """Phase 3 inline guard for PUT/DELETE on a dashboard."""
    from backend.governance.contract import require as governance_require
    governance_require(
        user=current_user,
        action="update",
        resource={
            "type": "dashboard",
            "org_id": str(dashboard.org_id) if dashboard.org_id else None,
            "owner_user_id": str(dashboard.user_id) if dashboard.user_id else None,
        },
    )


def _dashboard_to_response(dashboard: Dashboard) -> DashboardResponse:
    return DashboardResponse(
        id=dashboard.id,
        title=dashboard.title,
        description=dashboard.description,
        widgets=dashboard.widgets or [],
        data_context=dashboard.data_context,
        created_at=str(dashboard.created_at),
        updated_at=str(dashboard.updated_at),
        schedule_type=dashboard.schedule_type,
        schedule_value=dashboard.schedule_value,
        cron_expression=dashboard.cron_expression,
        schedule_active=dashboard.schedule_active or False,
        next_run_at=str(dashboard.next_run_at) if dashboard.next_run_at else None,
        last_run_at=str(dashboard.last_run_at) if dashboard.last_run_at else None,
    )


@router.get("", response_model=List[DashboardResponse])
async def list_dashboards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List dashboards visible to the current user.

    Phase 3 collaborative workspace: every member of the caller's org sees
    every dashboard in the org. Legacy callers without an org_id keep the
    owner-only view.
    """
    dashboards = _dashboard_visible_to(db.query(Dashboard), current_user).all()
    return [_dashboard_to_response(d) for d in dashboards]


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific dashboard."""
    dashboard = (
        _dashboard_visible_to(db.query(Dashboard), current_user)
        .filter(Dashboard.id == dashboard_id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return _dashboard_to_response(dashboard)


@router.post("", response_model=DashboardResponse, status_code=status.HTTP_201_CREATED)
async def create_dashboard(
    payload: DashboardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new dashboard."""
    dashboard = Dashboard(
        user_id=current_user.id,
        org_id=current_user.org_id,
        title=payload.title,
        description=payload.description,
        widgets=payload.widgets,
    )
    db.add(dashboard)
    db.commit()
    db.refresh(dashboard)

    # If the Org is cut over to DuckDB serving, the agent emits DuckDB SQL, so
    # mark this dashboard born-DuckDB: it's never re-transpiled and serving may
    # use the DuckDB path immediately (Phase 3 cutover gate).
    if current_user.org_id:
        try:
            from backend.config.feature_flags import enabled
            if enabled(str(current_user.org_id), "duckdb_widget_serving"):
                from backend.migration.dialect_migration import mark_born_duckdb
                mark_born_duckdb(dashboard.id, db)
        except Exception:
            logger.warning("mark_born_duckdb failed for dashboard %s", dashboard.id, exc_info=True)

    return _dashboard_to_response(dashboard)


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: int,
    payload: DashboardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a dashboard (partial update)."""
    dashboard = (
        _dashboard_visible_to(db.query(Dashboard), current_user)
        .filter(Dashboard.id == dashboard_id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    _governance_require_mutate_dashboard(current_user, dashboard)

    if payload.title is not None:
        dashboard.title = payload.title
    if payload.description is not None:
        dashboard.description = payload.description
    if payload.widgets is not None:
        dashboard.widgets = payload.widgets

    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_response(dashboard)


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Hard delete a dashboard."""
    dashboard = (
        _dashboard_visible_to(db.query(Dashboard), current_user)
        .filter(Dashboard.id == dashboard_id)
        .first()
    )
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    _governance_require_mutate_dashboard(current_user, dashboard)

    db.delete(dashboard)
    db.commit()
