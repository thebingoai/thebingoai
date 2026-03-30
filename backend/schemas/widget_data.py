from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class FilterParam(BaseModel):
    column: str = Field(..., pattern=r'^[a-zA-Z_][a-zA-Z0-9_.]*$')
    op: str = Field(..., pattern=r'^(eq|neq|gt|gte|lt|lte|ilike|in)$')
    value: Any


class WidgetRefreshRequest(BaseModel):
    connection_id: int
    sql: str = Field(..., min_length=1, max_length=10000)
    mapping: Dict[str, Any]
    filters: Optional[List[FilterParam]] = None
    dashboard_id: Optional[int] = None        # For dimension-aware filter injection
    widget_sources: Optional[List[str]] = None  # Sources this widget uses (from data_context)


class WidgetRefreshResponse(BaseModel):
    config: Dict[str, Any]
    execution_time_ms: float
    row_count: int
    truncated: bool = False
    refreshed_at: str
    source_columns: List[str] = []
    source_rows: List[List[Any]] = []


class BulkRefreshResponse(BaseModel):
    # widgetId -> {config, refreshed_at} on success, or {error} on failure
    widgets: Dict[str, Any]


class WidgetSuggestFixRequest(BaseModel):
    connection_id: int
    sql: str = Field(..., min_length=1, max_length=10000)
    error_message: str = Field(..., min_length=1, max_length=5000)
    mapping: Dict[str, Any]
    widget_title: Optional[str] = None
    widget_description: Optional[str] = None


class WidgetSuggestFixResponse(BaseModel):
    suggested_sql: str
    explanation: str
