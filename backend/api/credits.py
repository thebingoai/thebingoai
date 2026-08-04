from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.services.token_tracking_service import _default_user_daily_credits
from datetime import datetime, date, timedelta, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/credits", tags=["credits"])


class BalanceResponse(BaseModel):
    used_today: int
    remaining: int
    resets_at: str
    org_exhausted: bool = False  # workspace credit pool drained (trial expiry / spent)
    org_recurring: int = 0       # derived: total - topup
    org_topup: int = 0
    org_total: int = 0
    # Tells the frontend how to read `remaining` instead of inferring it:
    #   "workspace" → org pool total (recurring + topup), gates spending.
    #   "unlimited" → no org pool; the daily cap was removed, so nothing gates
    #                 this user. `remaining` is not a real limit — hide it.
    balance_scope: str = "unlimited"


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # ponytail: `daily_limit` gates nothing and is no longer part of the
    # response; it only backs `remaining` in the no-org-pool branch below.
    # Drop this read when the column itself is dropped.
    row = db.execute(
        text("SELECT daily_limit FROM user_credit_balances WHERE user_id = :uid"),
        {"uid": str(current_user.id)}
    ).fetchone()
    daily_limit = row.daily_limit if row else _default_user_daily_credits()

    today = date.today()
    used_row = db.execute(
        text("SELECT COALESCE(SUM(credits_used), 0) AS used FROM credit_usage WHERE user_id = :uid AND date = :today"),
        {"uid": str(current_user.id), "today": today}
    ).fetchone()
    used_today = int(used_row.used)

    # Daily limit removed — the bottom-left balance reflects the workspace (org)
    # credit pool, but ONLY where something actually debits that pool. Gating and
    # per-turn debit live exclusively in the enterprise bingo-admin manager; the
    # community manager is stats-only (it pays its own LLM provider via its own
    # API keys). Reporting "workspace" without a debiting manager would render a
    # balance that never moves and an org_exhausted that never trips, so the
    # scope is decided by whether that plugin is loaded.
    from backend.plugins.loader import get_loaded_plugins
    from backend.services.org_credit_pool import read_org_pool_breakdown, lookup_user_org_id
    org_exhausted = False
    org_recurring = org_topup = org_total = 0
    # No org pool (community / no-org user): the daily cap was removed, so nothing
    # gates this user — they are unlimited. `remaining` carries the legacy daily
    # figure only for the settings consumption view; the chat UI hides it because
    # balance_scope == "unlimited". Enterprise users always resolve to a pool.
    remaining = max(0, daily_limit - used_today)
    balance_scope = "unlimited"
    org_id = (
        lookup_user_org_id(db, current_user.id)
        if "bingo-admin" in get_loaded_plugins()
        else None
    )
    if org_id is not None:
        breakdown = read_org_pool_breakdown(db, org_id)
        if breakdown is not None:
            org_recurring = breakdown["recurring"]
            org_topup = breakdown["topup"]
            org_total = breakdown["total"]
            remaining = max(0, org_total)
            balance_scope = "workspace"
            if org_total <= 0:
                org_exhausted = True

    tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
    resets_at = tomorrow.replace(tzinfo=timezone.utc).isoformat()

    return BalanceResponse(
        used_today=used_today,
        remaining=remaining,
        resets_at=resets_at,
        org_exhausted=org_exhausted,
        org_recurring=org_recurring,
        org_topup=org_topup,
        org_total=org_total,
        balance_scope=balance_scope,
    )


CREDIT_PACKAGES = {"10k": 10000}  # TODO: payment gateway — stub-confirmed for now

_TRUTHY = {"1", "true", "yes", "on"}


def _self_serve_topup_enabled() -> bool:
    # Disabled by default: this is a stub template with no payment gateway, so
    # leaving it callable would let any user mint free credits. Flip the env var
    # ON only once a real payment flow gates the grant.
    import os
    return os.environ.get("SELF_SERVE_TOPUP_ENABLED", "false").strip().lower() in _TRUTHY


class BuyRequest(BaseModel):
    package: str


@router.post("/buy", response_model=BalanceResponse)
async def buy_credits(
    body: BuyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException
    if not _self_serve_topup_enabled():
        # No payment gateway wired yet — refuse so the stub can't grant free credits.
        raise HTTPException(status_code=403, detail="Self-serve top-up is not enabled.")
    amount = CREDIT_PACKAGES.get(body.package)
    if amount is None:
        raise HTTPException(status_code=400, detail=f"Unknown package: {body.package}")

    from backend.services.org_credit_pool import lookup_user_org_id
    org_id = lookup_user_org_id(db, current_user.id)
    if org_id is None:
        raise HTTPException(status_code=400, detail="No workspace to credit")

    # TODO: payment gateway charge/confirmation goes here. Stub: credit immediately.
    db.execute(
        text(
            "UPDATE organizations "
            "SET topup_balance = topup_balance + :amt, "
            "    credit_balance = credit_balance + :amt "
            "WHERE id = :org"
        ),
        {"amt": int(amount), "org": str(org_id)},
    )
    db.execute(
        text(
            "INSERT INTO org_credit_topups (org_id, amount, note, created_at) "
            "VALUES (:org, :amount, :note, :now)"
        ),
        {"org": str(org_id), "amount": int(amount), "note": "self-serve", "now": datetime.utcnow()},
    )
    db.commit()
    # Reuse the balance handler for a consistent response shape (fresh breakdown).
    return await get_balance(current_user=current_user, db=db)
