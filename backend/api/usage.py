"""Usage analytics API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.usage import UsageSummaryResponse, DailyUsageResponse
from backend.services.token_tracking_service import TokenTrackingService
from datetime import datetime, timedelta

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to summarize"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get token usage summary for current user."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    summary = TokenTrackingService.get_user_usage_summary(
        db, current_user.id, start_date, end_date
    )

    return summary


@router.get("/daily", response_model=DailyUsageResponse)
async def get_daily_usage(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get daily token usage breakdown."""
    daily_usage = TokenTrackingService.get_daily_usage(db, current_user.id, days)

    return DailyUsageResponse(daily_usage=daily_usage)
