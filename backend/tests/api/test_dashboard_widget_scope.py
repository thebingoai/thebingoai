"""Read scope on GET /dashboards/{dashboard_id}/widgets/{widget_id}.

The endpoint (in briefings.py — it predates chat charts) was owner-only while
`GET /dashboards/{id}`, the list the mention picker and briefing UI are built
from, is org-wide. A chat message embedding a live widget of an org-mate's
dashboard therefore rendered nothing: the fetch 404'd and the embed silently
dropped itself.

Same SQLite fixture as test_refresh_visibility.py, so the or_/subquery predicate
actually runs.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, JSON, LargeBinary
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import BYTEA, JSONB

from backend.api.briefings import get_dashboard_widget
from backend.database.base import Base
from backend.models.dashboard import Dashboard
from backend.models.organization import Organization
from backend.models.user import User


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="function")
def db():
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
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def seeded(db):
    widget = {"id": "w-1", "widget": {"type": "chart", "config": {"title": "Revenue"}}}
    db.add_all([
        Organization(id="org-1", name="Org 1", feature_flags={}),
        Organization(id="org-2", name="Org 2", feature_flags={}),
        User(id="u-owner", email="owner@x.test", org_id="org-1"),
        User(id="u-member", email="member@x.test", org_id="org-1"),
        User(id="u-outsider", email="outsider@x.test", org_id="org-2"),
        Dashboard(user_id="u-owner", org_id="org-1", title="Org dash", widgets=[widget]),
    ])
    db.commit()
    users = {u.id: u for u in db.query(User).all()}
    return db.query(Dashboard).first(), users


def _get(db, dashboard, user, widget_id="w-1"):
    return _run(get_dashboard_widget(dashboard.id, widget_id, user, db))


def test_owner_gets_the_widget(db, seeded):
    dashboard, users = seeded
    assert _get(db, dashboard, users["u-owner"])["id"] == "w-1"


def test_org_member_gets_the_widget(db, seeded):
    """The regression: readable via GET /dashboards, 404 here."""
    dashboard, users = seeded
    assert _get(db, dashboard, users["u-member"])["id"] == "w-1"


def test_other_org_user_gets_404(db, seeded):
    dashboard, users = seeded
    with pytest.raises(HTTPException) as exc:
        _get(db, dashboard, users["u-outsider"])
    assert exc.value.status_code == 404


def test_unknown_widget_id_still_404s_for_a_reader(db, seeded):
    dashboard, users = seeded
    with pytest.raises(HTTPException) as exc:
        _get(db, dashboard, users["u-member"], widget_id="w-nope")
    assert exc.value.status_code == 404
