"""Phase 4 of multi-user-org: org credit pool consumption.

Exercises ``backend.services.org_credit_pool`` against a real Postgres engine
(seeded by ``conftest.test_engine``) so the atomic UPDATE ... RETURNING path
matches production semantics, then verifies CreditContextManager honours both
the per-user daily cap and the org pool.
"""
from __future__ import annotations

import uuid

import pytest

from backend.models.organization import Organization
from backend.models.user import User
from backend.services.org_credit_pool import (
    check_org_pool,
    lookup_user_org_id,
    try_decrement_org_pool,
)
from backend.services.token_tracking_service import (
    CreditContextManager,
    InsufficientCreditsError,
)


def _mk_org(db, *, balance: int = 5000) -> Organization:
    o = Organization(
        id=str(uuid.uuid4()),
        name=f"acme-{uuid.uuid4()}",
        credit_balance=balance,
    )
    db.add(o)
    db.commit()
    return o


def _mk_user(db, *, org_id: str | None) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4()}@example.com",
        auth_provider="sso",
        org_id=org_id,
    )
    db.add(u)
    db.commit()
    return u


class TestOrgCreditPoolHelpers:

    def test_lookup_user_org_id(self, db_session):
        org = _mk_org(db_session)
        user = _mk_user(db_session, org_id=org.id)
        assert lookup_user_org_id(db_session, user.id) == org.id

    def test_check_org_pool_returns_balance(self, db_session):
        org = _mk_org(db_session, balance=42)
        assert check_org_pool(db_session, org.id) == 42

    def test_try_decrement_org_pool_returns_new_balance(self, db_session):
        org = _mk_org(db_session, balance=10)
        assert try_decrement_org_pool(db_session, org.id, amount=3) == 7
        assert check_org_pool(db_session, org.id) == 7

    def test_try_decrement_returns_none_when_exhausted(self, db_session):
        org = _mk_org(db_session, balance=0)
        assert try_decrement_org_pool(db_session, org.id) is None
        # Untouched.
        assert check_org_pool(db_session, org.id) == 0


class TestCreditContextManagerOrgPool:

    def test_under_both_caps_succeeds(self, db_session):
        org = _mk_org(db_session, balance=5)
        user = _mk_user(db_session, org_id=org.id)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        mgr._check()
        mgr._record()
        assert check_org_pool(db_session, org.id) == 4

    def test_org_pool_exhausted_blocks_with_org_pool_reason(self, db_session):
        org = _mk_org(db_session, balance=0)
        user = _mk_user(db_session, org_id=org.id)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        with pytest.raises(InsufficientCreditsError) as ex:
            mgr._check()
        assert ex.value.reason == "org_pool"

    def test_user_daily_cap_blocks_with_user_daily_reason(self, db_session):
        org = _mk_org(db_session, balance=100)
        user = _mk_user(db_session, org_id=org.id)
        # Seed a 0 daily_limit so the per-user cap fires before the org check.
        from sqlalchemy import text
        from datetime import datetime
        db_session.execute(
            text(
                "INSERT INTO user_credit_balances (user_id, daily_limit, created_at) "
                "VALUES (:uid, 0, :now)"
            ),
            {"uid": user.id, "now": datetime.utcnow()},
        )
        db_session.commit()

        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        with pytest.raises(InsufficientCreditsError) as ex:
            mgr._check()
        assert ex.value.reason == "user_daily"

    def test_user_without_org_skips_pool_check(self, db_session):
        # Community / legacy user. Pool branch must be inert.
        user = _mk_user(db_session, org_id=None)
        mgr = CreditContextManager(
            db=db_session,
            user_id=user.id,
            title="t",
            provider_name="anthropic",
            conversation_id=None,
        )
        # No exception — pool branch skipped.
        mgr._check()
        mgr._record()
