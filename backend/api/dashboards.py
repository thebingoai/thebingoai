from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any
from backend.database.session import get_db
from backend.api.auth import get_current_user
from backend.models.user import User
from backend.models.dashboard import Dashboard

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
    created_at: str
    updated_at: str
    schedule_type: Optional[str] = None
    schedule_value: Optional[str] = None
    cron_expression: Optional[str] = None
    schedule_active: bool = False
    next_run_at: Optional[str] = None
    last_run_at: Optional[str] = None


def _dashboard_to_response(dashboard: Dashboard) -> DashboardResponse:
    return DashboardResponse(
        id=dashboard.id,
        title=dashboard.title,
        description=dashboard.description,
        widgets=dashboard.widgets or [],
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
    """List all dashboards for the current user."""
    dashboards = db.query(Dashboard).filter(
        Dashboard.user_id == current_user.id,
    ).all()
    return [_dashboard_to_response(d) for d in dashboards]


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific dashboard."""
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()
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
        title=payload.title,
        description=payload.description,
        widgets=payload.widgets,
    )
    db.add(dashboard)
    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_response(dashboard)


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: int,
    payload: DashboardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a dashboard (partial update)."""
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

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
    dashboard = db.query(Dashboard).filter(
        Dashboard.id == dashboard_id,
        Dashboard.user_id == current_user.id,
    ).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    db.delete(dashboard)
    db.commit()
