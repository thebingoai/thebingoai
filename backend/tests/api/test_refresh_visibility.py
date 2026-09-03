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
from types import SimpleNamespace
from unittest.mock import MagicMock

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


# ── refresh_widget (single endpoint) on a shared dashboard ───────────────────

OPTIONS_SQL = "SELECT DISTINCT region AS option_value FROM t"
WIDGET_SQL = "SELECT COUNT(*) AS v FROM t"


def _shared_setup(db, seeded, monkeypatch):
    """Make org-2's viewer a reader of org-1, and give org-1 a connection.

    The dashboard carries the two query shapes a viewer's browser legitimately
    replays: a widget's own `dataSource`, and a filter control's `optionsSource`.
    """
    from backend.models.database_connection import DatabaseConnection
    import backend.api.dashboards as dashboards_api

    conn = DatabaseConnection(
        id=77, user_id="u-owner", org_id="org-1", name="host db",
        db_type="postgres", host="h", port=5432, database="d", username="u",
    )
    conn._encrypted_password = "x"
    # A second connection in the same org, owned by org-1's own member: the
    # non-shared branch of _readable_connection requires the caller to own it.
    own = DatabaseConnection(
        id=78, user_id="u-member", org_id="org-1", name="member db",
        db_type="postgres", host="h", port=5432, database="d", username="u",
    )
    own._encrypted_password = "x"
    db.add_all([conn, own])
    seeded["dashboard"].widgets = [
        {
            "id": "w-filter",
            "widget": {"type": "filter", "config": {"controls": [{
                "type": "dropdown", "key": "region", "column": "region",
                "optionsSource": {"connectionId": 77, "sql": OPTIONS_SQL},
            }]}},
        },
        {
            "id": "w-kpi",
            "widget": {"type": "kpi", "config": {}},
            "dataSource": {"connectionId": 77, "sql": WIDGET_SQL,
                           "mapping": {"type": "kpi", "valueColumn": "v"}},
        },
    ]
    db.commit()
    monkeypatch.setattr(
        dashboards_api, "_readable_org_ids", lambda _db, user: {"org-1", "org-2"},
    )
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(
        wd, "_read_widget_from_cache",
        lambda dash_id, wid, org_id, user_id, plane=None: None,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda r, m: {"rows": []})

    connector = MagicMock()
    connector.serves_from_plane = False
    connector.execute_query.return_value = SimpleNamespace(
        columns=["v"], rows=[(1,)], row_count=1, execution_time_ms=1.0, truncated=False,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda c, db=None: connector,
    )
    return connector


def test_shared_viewer_gets_filter_options_when_dashboard_id_is_sent(db, seeded, monkeypatch):
    """The dropdown-options and date-bounds queries go through this endpoint. With
    dashboard_id the shared branch of _readable_connection resolves the HOST org's
    connection, exactly as the dashboard's own widgets do."""
    _shared_setup(db, seeded, monkeypatch)
    req = wd.WidgetRefreshRequest(
        connection_id=77, sql=OPTIONS_SQL,
        mapping={"type": "table", "columnConfig": [{"column": "option_value"}]},
        dashboard_id=seeded["dashboard"].id,
    )
    resp = _run(wd.refresh_widget(req, seeded["outsider"], db))
    assert resp.config == {"rows": []}


def test_shared_viewer_404s_without_dashboard_id(db, seeded, monkeypatch):
    """Without it the endpoint resolves no dashboard, so the owner-only branch
    runs and a permitted cross-org viewer is refused — the widgets render while
    their filter controls silently fall back to empty."""
    _shared_setup(db, seeded, monkeypatch)
    req = wd.WidgetRefreshRequest(
        connection_id=77, sql=OPTIONS_SQL,
        mapping={"type": "table", "columnConfig": [{"column": "option_value"}]},
    )
    with pytest.raises(HTTPException) as exc:
        _run(wd.refresh_widget(req, seeded["outsider"], db))
    assert exc.value.status_code == 404


# ── shared dashboards run only the SQL they store ────────────────────────────

def test_shared_viewer_cannot_run_sql_the_dashboard_does_not_store(db, seeded, monkeypatch):
    """The shared branch of _readable_connection authorizes any connection in
    the host org, and the request's SQL is executed verbatim against it — on the
    DuckDB path under a system_context that bypasses per-table grants. A viewer
    of one shared dashboard could read every table the host org has connected."""
    connector = _shared_setup(db, seeded, monkeypatch)
    req = wd.WidgetRefreshRequest(
        connection_id=77, sql="SELECT * FROM salaries",
        mapping={"type": "table", "columnConfig": [{"column": "amount"}]},
        dashboard_id=seeded["dashboard"].id,
    )
    with pytest.raises(HTTPException) as exc:
        _run(wd.refresh_widget(req, seeded["outsider"], db))
    assert exc.value.status_code == 403
    connector.execute_query.assert_not_called()


def test_shared_viewer_runs_a_stored_widget_query(db, seeded, monkeypatch):
    """A widget's own SQL still serves, and a trailing semicolon is not a
    different query."""
    _shared_setup(db, seeded, monkeypatch)
    req = wd.WidgetRefreshRequest(
        connection_id=77, sql=WIDGET_SQL + ";",
        mapping={"type": "kpi", "valueColumn": "v"},
        dashboard_id=seeded["dashboard"].id,
    )
    resp = _run(wd.refresh_widget(req, seeded["outsider"], db))
    assert resp.config == {"rows": []}


def test_stored_sql_on_another_connection_is_still_refused(db, seeded, monkeypatch):
    """The pair is (connection, SQL): replaying a stored query against a
    different host-org connection reads a different database."""
    _shared_setup(db, seeded, monkeypatch)
    req = wd.WidgetRefreshRequest(
        connection_id=99, sql=WIDGET_SQL,
        mapping={"type": "kpi", "valueColumn": "v"},
        dashboard_id=seeded["dashboard"].id,
    )
    with pytest.raises(HTTPException) as exc:
        _run(wd.refresh_widget(req, seeded["outsider"], db))
    assert exc.value.status_code == 403


def test_member_inside_the_host_workspace_keeps_free_sql(db, seeded, monkeypatch):
    """Scoped to read-only viewers: a caller whose *active* org is the
    dashboard's can already edit it, and the widget editor previews arbitrary
    SQL before the widget is saved."""
    _shared_setup(db, seeded, monkeypatch)
    req = wd.WidgetRefreshRequest(
        connection_id=78, sql="SELECT * FROM anything_at_all",
        mapping={"type": "table", "columnConfig": [{"column": "v"}]},
        dashboard_id=seeded["dashboard"].id,
    )
    resp = _run(wd.refresh_widget(req, seeded["member"], db))
    assert resp.config == {"rows": []}
