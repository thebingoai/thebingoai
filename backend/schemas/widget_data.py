from pydantic import BaseModel, Field, field_validator
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
    widget_id: Optional[str] = None           # For DataPlane cache reads
    widget_sources: Optional[List[str]] = None  # Sources this widget uses (from data_context)

    @field_validator("widget_id", mode="before")
    @classmethod
    def _coerce_widget_id(cls, v):
        # Agent-generated dashboards store numeric widget ids; accept them.
        # Everything else falls through to normal str validation.
        if isinstance(v, int) and not isinstance(v, bool):
            return str(v)
        return v


class WidgetRefreshResponse(BaseModel):
    config: Dict[str, Any]
    execution_time_ms: float
    row_count: int
    truncated: bool = False
    refreshed_at: str
    source_columns: List[str] = []
    source_rows: List[List[Any]] = []
    # Where the rows came from. "data_plane" = DuckDB over Parquet (local or GCS).
    # "cache" = warm _dash_* materialized cache. "source" = live connector
    # (fallback). Frontend uses this to render a "Parquet • synced X ago" badge
    # when the read served from the DataPlane.
    served_from: str = "source"


class BulkRefreshRequest(BaseModel):
    # Optional dashboard-level filters applied to every widget, mirroring the
    # single-widget refresh. None/empty = unfiltered (warm-cache eligible).
    filters: Optional[List[FilterParam]] = None


class BulkRefreshResponse(BaseModel):
    # widgetId -> {config, refreshed_at, served_from, truncated} on success,
    # or {error} — the store records the latter per widget so the widget can
    # show it instead of silently keeping its previous value.
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
