"""Pydantic schemas for heartbeat jobs system."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# Preset schedule -> cron expression mapping
_PRESET_MAP = {
    "5m": "*/5 * * * *",
    "15m": "*/15 * * * *",
    "30m": "*/30 * * * *",
    "1h": "0 * * * *",
    "2h": "0 */2 * * *",
    "6h": "0 */6 * * *",
    "12h": "0 */12 * * *",
    "daily": "0 9 * * *",
    "weekly": "0 9 * * 1",
    "weekdays": "0 9 * * 1-5",
}


def resolve_cron_expression(schedule_type: str, schedule_value: str) -> str:
    """Convert schedule_type + schedule_value to a normalized cron expression."""
    if schedule_type == "preset":
        cron = _PRESET_MAP.get(schedule_value)
        if not cron:
            raise ValueError(f"Unknown preset schedule: {schedule_value}. Valid: {list(_PRESET_MAP.keys())}")
        return cron
    elif schedule_type == "cron":
        from croniter import croniter
        if not croniter.is_valid(schedule_value):
            raise ValueError(f"Invalid cron expression: {schedule_value}")
        return schedule_value
    else:
        raise ValueError(f"schedule_type must be 'preset' or 'cron', got: {schedule_type}")


class HeartbeatJobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    prompt: str = Field(..., min_length=1, max_length=10000)
    schedule_type: str = Field(..., pattern="^(preset|cron)$")
    schedule_value: str = Field(..., min_length=1, max_length=100)

    @field_validator("schedule_value")
    @classmethod
    def validate_schedule_value(cls, v: str, info) -> str:
        schedule_type = info.data.get("schedule_type")
        if schedule_type:
            resolve_cron_expression(schedule_type, v)  # raises ValueError if invalid
        return v


class HeartbeatJobUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    prompt: Optional[str] = Field(None, min_length=1, max_length=10000)
    schedule_type: Optional[str] = Field(None, pattern="^(preset|cron)$")
    schedule_value: Optional[str] = Field(None, min_length=1, max_length=100)


class HeartbeatJobToggle(BaseModel):
    is_active: bool


class HeartbeatJobResponse(BaseModel):
    id: str
    name: str
    prompt: str
    schedule_type: str
    schedule_value: str
    cron_expression: str
    is_active: bool
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HeartbeatJobRunResponse(BaseModel):
    id: str
    job_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    prompt: Optional[str]
    response: Optional[str]
    error: Optional[str]
    duration_ms: Optional[int]

    model_config = {"from_attributes": True}


class HeartbeatJobRunListResponse(BaseModel):
    runs: List[HeartbeatJobRunResponse]
    total: int
