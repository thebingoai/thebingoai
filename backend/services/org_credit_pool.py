"""Org-level credit pool helpers.

Phase 4 of multi-user-org. Each chat turn debits both:

  - the per-user daily credit balance (legacy, owned by token_tracking_service),
  - and the per-org credit balance (this module).

Either exhausted → block the turn. Both succeed → record + commit atomically.

The org pool defaults to 5000 credits per org (set in alembic migration
h0i1j2k3l4m5_org_credits_and_role_rename); BingoAdmin tops it up via the
forthcoming Phase 5 admin UI.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def lookup_user_org_id(db: Session, user_id: str) -> Optional[str]:
    """Return the user's `org_id` or None when unset / missing.

    Wrapped in a defensive try/except so community deployments that lack the
    organizations FK column (pre-Phase-0) still work.
    """
    try:
        row = db.execute(
            text("SELECT org_id FROM users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return row[0]


def check_org_pool(db: Session, org_id: str) -> Optional[int]:
    """Read-only check of the org credit balance.

    Returns the current balance, or None when the column / row is missing
    (community deployments without Phase 0 schema applied).
    """
    try:
        row = db.execute(
            text("SELECT credit_balance FROM organizations WHERE id = :org"),
            {"org": str(org_id)},
        ).fetchone()
    except Exception:
        return None
    return int(row[0]) if row is not None else None


def try_decrement_org_pool(db: Session, org_id: str, amount: int = 1) -> Optional[int]:
    """Atomically decrement the org's credit_balance by `amount`.

    Returns the new balance on success, or None if there weren't enough
    credits (the UPDATE's WHERE clause failed the >= check). The caller
    owns the surrounding transaction; this function only flushes.
    """
    try:
        result = db.execute(
            text(
                "UPDATE organizations "
                "SET credit_balance = credit_balance - :amt "
                "WHERE id = :org AND credit_balance >= :amt "
                "RETURNING credit_balance"
            ),
            {"amt": int(amount), "org": str(org_id)},
        )
    except Exception:
        # Column missing (community pre-Phase-0) — treat as "no pool gating".
        return None
    row = result.fetchone()
    if row is None:
        return None
    return int(row[0])
