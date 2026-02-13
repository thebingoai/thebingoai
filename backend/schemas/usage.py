"""Pydantic schemas for usage tracking."""

from pydantic import BaseModel
from typing import Dict, Any, List


class UsageSummaryResponse(BaseModel):
    user_id: str
    period: Dict[str, str]  # {start, end}
    totals: Dict[str, Any]  # {operations, tokens, cost}
    by_operation: Dict[str, Dict[str, Any]]  # {operation_name: {count, tokens, cost}}


class DailyUsageEntry(BaseModel):
    date: str
    tokens: int
    cost: float
    operations: int


class DailyUsageResponse(BaseModel):
    daily_usage: List[DailyUsageEntry]
