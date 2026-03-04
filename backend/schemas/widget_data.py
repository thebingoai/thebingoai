from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


class WidgetRefreshRequest(BaseModel):
    connection_id: int
    sql: str = Field(..., min_length=1, max_length=10000)
    mapping: Dict[str, Any]
    limit: int = Field(default=100, ge=1, le=1000)


class WidgetRefreshResponse(BaseModel):
    config: Dict[str, Any]
    execution_time_ms: float
    row_count: int
    truncated: bool = False
    refreshed_at: str


class BulkRefreshResponse(BaseModel):
    # widgetId -> {config, refreshed_at} on success, or {error} on failure
    widgets: Dict[str, Any]
