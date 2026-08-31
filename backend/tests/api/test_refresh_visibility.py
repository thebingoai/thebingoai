"""Org-wide visibility on the widget refresh endpoints.

Refresh endpoints share `_dashboard_visible_to` with GET /dashboards/{id}:
any org member who can view a dashboard can refresh its widgets. Previously
the refresh handlers were owner-only, so non-owner org members got a 404 on
dashboards they could see.

Uses a real SQLite session (mirrors test_feature_flags.py) so the
outerjoin/or_ predicate is actually exercised, not mocked.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, JSON, LargeBinary
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

from backend.database.base import Base
from backend.models.organization import Organization
from backend.models.user import User
from backend.models.dashboard import Dashboard
from backend.api.dashboards import _dashboard_visible_to
from backend.api import widget_data as wd


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="function")
def db():
    # `refresh_dashboard_widgets` hands its Session to a worker thread
    # (`asyncio.to_thread`). SQLite rejects a cross-thread handle by default, and
    # its default memory pool is per-thread — the worker would otherwise open a
    # second, empty database. Neither applies to the Postgres this runs on in
    # production; both are artifacts of the in-memory fixture.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
                col.server_default = None
            elif isinstance(col.type, BYTEA):
                col.type = LargeBinary()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def seeded(db):
    org = Organization(id="org-1", name="Org 1", feature_flags={})
    other_org = Organization(id="org-2", name="Org 2", feature_flags={})
    owner = User(id="u-owner", email="owner@x.test", org_id="org-1")
    member = User(id="u-member", email="member@x.test", org_id="org-1")
    outsider = User(id="u-outsider", email="outsider@x.test", org_id="org-2")
    loner = User(id="u-loner", email="loner@x.test", org_id=None)
    dashboard = Dashboard(user_id="u-owner", org_id="org-1", title="Org dash", widgets=[])
    db.add_all([org, other_org, owner, member, outsider, loner, dashboard])
    db.commit()
    return {
        "owner": owner,
        "member": member,
        "outsider": outsider,
        "loner": loner,
        "dashboard": dashboard,
    }


# ── _dashboard_visible_to predicate ──────────────────────────────────────────

def test_org_member_sees_org_dashboard(db, seeded):
    found = (
        _dashboard_visible_to(db.query(Dashboard), seeded["member"], db)
        .filter(Dashboard.id == seeded["dashboard"].id)
        .first()
    )
    assert found is not None


def test_other_org_user_does_not_see_dashboard(db, seeded):
    found = (
        _dashboard_visible_to(db.query(Dashboard), seeded["outsider"], db)
        .filter(Dashboard.id == seeded["dashboard"].id)
        .first()
    )
    assert found is None


def test_no_org_user_sees_only_own(db, seeded):
    found = (
        _dashboard_visible_to(db.query(Dashboard), seeded["loner"], db)
        .filter(Dashboard.id == seeded["dashboard"].id)
        .first()
    )
    assert found is None


# ── refresh_dashboard_widgets (bulk endpoint) ────────────────────────────────

def test_bulk_refresh_succeeds_for_non_owner_org_member(db, seeded, monkeypatch):
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    resp = _run(wd.refresh_dashboard_widgets(
        seeded["dashboard"].id, None, seeded["member"], db,
    ))
    assert resp.widgets == {}  # no SQL-backed widgets, but no 404 either


def test_bulk_refresh_404_for_other_org_user(db, seeded, monkeypatch):
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    with pytest.raises(HTTPException) as exc:
        _run(wd.refresh_dashboard_widgets(
            seeded["dashboard"].id, None, seeded["outsider"], db,
        ))
    assert exc.value.status_code == 404


# ── bulk_widget_loading flag exposure ────────────────────────────────────────

def test_list_and_detail_both_carry_bulk_flag(db, seeded, monkeypatch):
    """The LIST endpoint must expose the flag too: widgets can mount from list
    data before the detail fetch lands; a stale False would fire the legacy
    per-widget refreshes alongside the bulk request."""
    import backend.api.dashboards as dashboards_api
    monkeypatch.setattr(dashboards_api, "_bulk_widget_loading_for", lambda user: True)

    listed = dashboards_api.list_dashboards(db=db, current_user=seeded["member"])
    assert listed and all(d.bulk_widget_loading is True for d in listed)

    detail = dashboards_api.get_dashboard(
        seeded["dashboard"].id, db=db, current_user=seeded["member"]
    )
    assert detail.bulk_widget_loading is True
