"""Pydantic schemas for dashboard schedule and refresh run system."""

from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class DashboardScheduleUpdate(BaseModel):
    schedule_type: str
    schedule_value: str

    @field_validator("schedule_value")
    @classmethod
    def validate_schedule_value(cls, v: str, info) -> str:
        from backend.schemas.heartbeat import resolve_cron_expression
        schedule_type = info.data.get("schedule_type")
        if schedule_type:
            resolve_cron_expression(schedule_type, v)  # raises ValueError if invalid
        return v


class DashboardScheduleToggle(BaseModel):
    schedule_active: bool


class DashboardScheduleResponse(BaseModel):
    schedule_type: Optional[str]
    schedule_value: Optional[str]
    cron_expression: Optional[str]
    schedule_active: bool
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DashboardRefreshRunResponse(BaseModel):
    id: str
    dashboard_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    widgets_total: Optional[int]
    widgets_succeeded: Optional[int]
    widgets_failed: Optional[int]
    error: Optional[str]
    widget_errors: Optional[Dict[str, Any]]

    model_config = {"from_attributes": True}


class DashboardRefreshRunListResponse(BaseModel):
    runs: List[DashboardRefreshRunResponse]
    total: int
