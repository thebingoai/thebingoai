from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from datetime import datetime, date, timedelta, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/credits", tags=["credits"])


class BalanceResponse(BaseModel):
    daily_limit: int
    used_today: int
    remaining: int
    resets_at: str


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    row = db.execute(
        text("SELECT daily_limit FROM user_credit_balances WHERE user_id = :uid"),
        {"uid": str(current_user.id)}
    ).fetchone()
    daily_limit = row.daily_limit if row else 180

    today = date.today()
    used_row = db.execute(
        text("SELECT COALESCE(SUM(credits_used), 0) AS used FROM credit_usage WHERE user_id = :uid AND date = :today"),
        {"uid": str(current_user.id), "today": today}
    ).fetchone()
    used_today = int(used_row.used)

    remaining = max(0, daily_limit - used_today)
    tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
    resets_at = tomorrow.replace(tzinfo=timezone.utc).isoformat()

    return BalanceResponse(
        daily_limit=daily_limit,
        used_today=used_today,
        remaining=remaining,
        resets_at=resets_at
    )
