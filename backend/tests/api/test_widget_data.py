"""Tests for the widget plane-redirect path and bootstrap fallback.

Covers:
  - _duckdb_serving_enabled (flag gate)
  - _serve_widget_via_dataplane (local-plane cold/missing → None fallback,
    GCS reader None→None fallback, unregistered connection→None)
  - refresh_widget fallback chain (plane → cache → source DB)
  - Bootstrap policy: pg/mysql widget fallback to live source when plane
    data is cold/missing.

Heavy I/O (connector open, plane query, DB session) is patched out.  The
endpoint handler is async def, so each call goes through `asyncio.run(...)`.
"""
from __future__ import annotations

import asyncio
import sys
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.api import widget_data as wd


def _run(coro):
    return asyncio.run(coro)


@dataclass
class FakeQueryResult:
    columns: list[str]
    rows: list[tuple]
    row_count: int
    execution_time_ms: float = 1.0
    truncated: bool = False


# ── Helpers ──────────────────────────────────────────────────────────────────

class FakeConnection(SimpleNamespace):
    def __init__(self, **kwargs):
        defaults = dict(id=42, user_id="u-1", db_type="postgresql",
                         org_id="org-1")
        defaults.update(kwargs)
        super().__init__(**defaults)

class FakeDashboard(SimpleNamespace):
    def __init__(self):
        super().__init__(id=1, user_id="u-1", data_context={})


def _user(id_="u-1", org_id=None):
    return SimpleNamespace(id=id_, org_id=org_id)


def _db_with_first(*side):
    """Return a MagicMock db where any .query()…(.outerjoin/.filter)*….first()
    chain returns `side[0]`, then `side[1]`, etc. Callers that need both
    dashboard + connection lookups pass two values. The query mock is
    self-returning so chains of any depth (e.g. the org-visibility predicate's
    outerjoin + double filter) resolve to the same `.first`.

    Once `side` is exhausted every further `.first()` yields None rather than
    raising StopIteration — `_readable_connection` issues a second, shared-sample
    query whenever the ownership lookup misses."""
    db = MagicMock()
    q = db.query.return_value
    q.outerjoin.return_value = q
    q.filter.return_value = q
    if side:
        remaining = iter(list(side))
        q.first.side_effect = lambda *a, **k: next(remaining, None)
    return db


def _setup_plane_patch(monkeypatch, plane):
    """Patch get_plane_for_connection to return (plane, scope)."""
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda conn: (plane, SimpleNamespace()),
    )


def _setup_duckdb_ready(monkeypatch, ready: bool = True):
    monkeypatch.setattr(
        "backend.migration.dialect_migration.is_duckdb_ready",
        lambda dashboard_id, db: ready,
    )


def _setup_rewrite_noop(monkeypatch):
    """rewrite_table_refs / extract_table_refs live in sql_refs and are imported
    inside _serve_widget_via_dataplane — patch the source module."""
    monkeypatch.setattr(
        "backend.utils.sql_refs.rewrite_table_refs",
        # Real signature is (sql, mapping, allowed_schemas=None) -> (sql, ok).
        lambda sql, mapping, allowed_schemas=None: (sql, True),
    )
    monkeypatch.setattr(
        "backend.utils.sql_refs.extract_table_refs",
        lambda sql: {"orders"},
    )


def _noop_table_map(monkeypatch):
    monkeypatch.setattr(
        "backend.services.data_plane_service.plane_table_map",
        lambda conn, db: {},
    )


# ── _duckdb_serving_enabled ─────────────────────────────────────────────────

def test_duckdb_serving_enabled_false_when_no_org():
    assert wd._duckdb_serving_enabled(None) is False


def test_duckdb_serving_enabled_calls_feature_flags(monkeypatch):
    calls = {}

    def _enabled(org_id: str, flag: str) -> bool:
        calls["org_id"] = org_id
        calls["flag"] = flag
        return True

    monkeypatch.setattr("backend.config.feature_flags.enabled", _enabled)
    assert wd._duckdb_serving_enabled("org-1") is True
    assert calls == {"org_id": "org-1", "flag": "duckdb_widget_serving"}


# ── _build_widget_response ──────────────────────────────────────────────────

def test_build_widget_response_includes_source_rows(monkeypatch):
    def _transform(result, mapping):
        return {"value": mapping["valueColumn"], "label": "test"}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    result = FakeQueryResult(
        columns=["total"], rows=[(15,)], row_count=1,
    )
    mapping = {"type": "kpi", "valueColumn": "total"}
    resp = wd._build_widget_response(result, mapping)

    assert resp.config == {"value": "total", "label": "test"}
    assert resp.row_count == 1
    assert resp.source_columns == ["total"]
    assert resp.source_rows == [[15]]


# ── _serve_via_dataplane — connection not found ─────────────────────────────

def test_serve_via_dataplane_none_when_connection_not_found():
    db = _db_with_first(None)
    req = wd.WidgetRefreshRequest(connection_id=42, sql="SELECT 1", mapping={})
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


def test_serve_via_dataplane_none_when_not_duckdb_ready(monkeypatch):
    _setup_duckdb_ready(monkeypatch, ready=False)
    db = _db_with_first(FakeConnection())
    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


# ── Local plane — bootstrap policy (cold/missing → fallback) ───────────────

def test_serve_via_dataplane_local_plane_cold_table_returns_none(monkeypatch):
    """Bootstrap policy: when the local plane doesn't have the source table yet
    (cold/missing Parquet), return None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class ColdLocalPlane:
        def table_exists(self, scope, table):
            return False

    _setup_plane_patch(monkeypatch, ColdLocalPlane())
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT * FROM orders", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


def test_serve_via_dataplane_local_plane_warm_table_returns_response(monkeypatch):
    """When the local plane has the table, serve via GCS reader (same data path
    as local plane in _build_widget_response — the function signature + response
    shape is identical for both plane types)."""
    monkeypatch.setattr(
        "backend.migration.dialect_migration.is_duckdb_ready",
        lambda dashboard_id, db: True,
    )
    monkeypatch.setattr(
        "backend.utils.sql_refs.rewrite_table_refs",
        # Real signature is (sql, mapping, allowed_schemas=None) -> (sql, ok).
        lambda sql, mapping, allowed_schemas=None: (sql, True),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.plane_table_map",
        lambda conn, db: {},
    )

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)

    class FakeReader:
        def query(self, scope, sql):
            return result
        def close(self):
            pass

    # GCS plane (not LocalFilesystemDataPlane) → triggers reader path
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda conn: (SimpleNamespace(), SimpleNamespace()),
    )
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: FakeReader(),
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={}, dashboard_id=1,
    )
    resp = wd._serve_widget_via_dataplane(req, None, _user(), db)
    assert resp is not None
    assert resp.config["value"] == 15
    assert resp.row_count == 1
    assert resp.source_columns == ["cnt"]
    assert resp.source_rows == [[15]]


def test_serve_via_dataplane_local_plane_raises_returns_none(monkeypatch):
    """Bootstrap policy: plane.query exception → None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class FaultyPlane:
        def table_exists(self, scope, table):
            return True
        def query(self, scope, sql, params=None):
            raise RuntimeError("disk-full")

    _setup_plane_patch(monkeypatch, FaultyPlane())
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


# ── GCS plane — reader None / reader success / reader exception ─────────────

def test_serve_via_dataplane_gcs_reader_none_returns_none(monkeypatch):
    """GCS path: reader is None (residency-locked / customer / no-HMAC)
    → None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class FakeGCSPlane:
        pass

    _setup_plane_patch(monkeypatch, FakeGCSPlane())
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: None,
    )
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


def test_serve_via_dataplane_gcs_reader_success(monkeypatch):
    """GCS path with a valid reader: serve via DuckDB-over-GCS."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)

    class FakeReader:
        def query(self, scope, sql):
            return result
        def close(self):
            pass

    class FakeGCSPlane:
        pass

    _setup_plane_patch(monkeypatch, FakeGCSPlane())
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: FakeReader(),
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={}, dashboard_id=1,
    )
    resp = wd._serve_widget_via_dataplane(req, None, _user(), db)
    assert resp is not None
    assert resp.config["value"] == 15


def test_serve_via_dataplane_gcs_exception_returns_none(monkeypatch):
    """GCS path: query raises → None → fall back to source DB."""
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)

    class FaultyReader:
        def query(self, scope, sql):
            raise RuntimeError("GCS timeout")
        def close(self):
            pass

    class FakeGCSPlane:
        pass

    _setup_plane_patch(monkeypatch, FakeGCSPlane())
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: FaultyReader(),
    )
    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT 1", mapping={}, dashboard_id=1,
    )
    assert wd._serve_widget_via_dataplane(req, None, _user(), db) is None


# ── refresh_widget — fallback chain (plane → cache → source DB) ────────────

def test_refresh_widget_no_dashboard_falls_straight_to_source(monkeypatch):
    """When no dashboard_id is supplied, skip both the plane and cache paths
    and go directly to the source DB connector."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.return_value = result

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: fake_connector,
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    db = _db_with_first(FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
    )
    resp = _run(wd.refresh_widget(req, _user(), db))
    assert resp is not None
    assert resp.row_count == 1
    assert resp.source_rows == [[15]]
    fake_connector.execute_query.assert_called_once()


def test_refresh_widget_source_db_fallback_when_plane_returns_none(monkeypatch):
    """Bootstrap policy: when the plane redirect returns None (cold data),
    the endpoint falls back to live source DB query — widget still renders."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    monkeypatch.setattr(wd, "_serve_widget_via_dataplane",
                         lambda req, dash, user, db: None)
    monkeypatch.setattr(wd, "_read_widget_from_cache",
                         lambda dash_id, wid, org_id, user_id, plane=None: None)

    result = FakeQueryResult(columns=["cnt"], rows=[(15,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.return_value = result

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: fake_connector,
    )

    def _transform(result, mapping):
        return {"value": 15}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    # dashboard first(), connection second ()
    db = _db_with_first(FakeDashboard(), FakeConnection())

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
        dashboard_id=1, widget_id="kpi_1",
    )
    resp = _run(wd.refresh_widget(req, _user(org_id="org-1"), db))
    assert resp is not None
    assert resp.row_count == 1
    fake_connector.execute_query.assert_called_once()
    call_args = fake_connector.execute_query.call_args
    assert call_args[0][0] == "SELECT COUNT(*) FROM orders"


# ── refresh_dashboard_widgets — shared reader / connector reuse ─────────────

def _bulk_widget(wid, connection_id=42):
    return {
        "id": wid,
        "dataSource": {
            "connectionId": connection_id,
            "sql": "SELECT COUNT(*) FROM orders",
            "mapping": {"type": "kpi", "valueColumn": "total"},
        },
        "widget": {"config": {"type": "kpi"}},
    }


def test_bulk_refresh_uses_one_shared_reader_for_all_widgets(monkeypatch):
    """Core perf claim: a multi-widget dashboard builds the GCS reader ONCE
    (not once per widget), serves every widget through it, and closes it once."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    _setup_duckdb_ready(monkeypatch)
    _setup_rewrite_noop(monkeypatch)
    _noop_table_map(monkeypatch)
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_plane_for_connection",
        lambda conn: (SimpleNamespace(), SimpleNamespace()),  # non-local → prod reader branch
    )

    class _CountingReader:
        def __init__(self):
            self.query_calls = 0
            self.closed = False

        def query(self, scope, sql, params=None):
            self.query_calls += 1
            return FakeQueryResult(columns=["cnt"], rows=[(1,)], row_count=1)

        def close(self):
            self.closed = True

    reader = _CountingReader()
    factory_calls = {"n": 0}

    def _factory(scope, db):
        factory_calls["n"] += 1
        return reader

    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader", _factory,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w1"), _bulk_widget("w2"), _bulk_widget("w3")],
    )
    # endpoint dashboard lookup, then one connection lookup per widget inside _serve
    db = _db_with_first(dashboard, FakeConnection(), FakeConnection(), FakeConnection())

    resp = _run(wd.refresh_dashboard_widgets(1, None, _user(org_id="org-1"), db))

    assert factory_calls["n"] == 1          # ONE reader for the whole dashboard
    assert reader.query_calls == 3          # all three widgets served by it
    assert reader.closed is True            # closed once after the loop
    assert set(resp.widgets.keys()) == {"w1", "w2", "w3"}
    assert all("config" in resp.widgets[w] for w in ("w1", "w2", "w3"))
    assert all(resp.widgets[w]["served_from"] == "data_plane" for w in ("w1", "w2", "w3"))


def _capture_serve_readers(monkeypatch):
    """Replace _serve_widget_via_dataplane with a recorder of (conn_id, reader).

    Returns the list it appends to. Each call reports a served widget so the
    bulk loop takes the plane branch and never reaches the source fallback.
    """
    seen = []

    def _fake_serve(request, dashboard, current_user, db, reader=None):
        seen.append((request.connection_id, reader))
        return SimpleNamespace(
            config={"value": 1}, served_from="data_plane",
            refreshed_at=datetime.now(timezone.utc).isoformat(),
        )

    monkeypatch.setattr(wd, "_serve_widget_via_dataplane", _fake_serve)
    return seen


def _setup_bulk_sample_routing(monkeypatch, sample_ids):
    """Bulk-refresh harness whose shared-sample lookup returns `sample_ids`."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    _setup_duckdb_ready(monkeypatch)
    sentinel = SimpleNamespace(name="shared-reader", close=lambda: None)
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: sentinel,
    )
    seen = _capture_serve_readers(monkeypatch)
    # `.all()` serves the shared-sample id lookup at the top of the bulk loop.
    # It is also what _readable_org_ids reads, and that subscripts its rows —
    # so a namedtuple, which answers both `r.id` and `r[0]`.
    Row = namedtuple("Row", "id")
    db = _db_with_first(SimpleNamespace(id=1, user_id="u-1", data_context={}, widgets=[]))
    db.query.return_value.all.return_value = [Row(i) for i in sample_ids]
    return sentinel, seen, db


def test_bulk_refresh_sample_widget_gets_own_reader_not_shared(monkeypatch):
    """The shared reader is scoped to the CALLER's bucket; the sample lives in
    the Samples org bucket. Sample widgets must get reader=None so _serve builds
    a reader for the sample's own scope — anything else reads the wrong bucket."""
    sentinel, seen, db = _setup_bulk_sample_routing(monkeypatch, sample_ids=[99])
    db.query.return_value.first.side_effect = None
    db.query.return_value.first.return_value = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w_sample", connection_id=99),
                 _bulk_widget("w_own", connection_id=42)],
    )

    _run(wd.refresh_dashboard_widgets(1, None, _user(org_id="org-1"), db))

    assert dict(seen) == {99: None, 42: sentinel}


def test_bulk_refresh_sample_id_matches_when_widget_stores_it_as_string(monkeypatch):
    """Widgets JSONB may carry connectionId as a string while sample_conn_ids
    holds DB ints. Without the int() normalization the membership test silently
    goes false and the sample widget reads the caller's bucket."""
    sentinel, seen, db = _setup_bulk_sample_routing(monkeypatch, sample_ids=[99])
    db.query.return_value.first.side_effect = None
    db.query.return_value.first.return_value = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w_sample", connection_id="99")],
    )

    _run(wd.refresh_dashboard_widgets(1, None, _user(org_id="org-1"), db))

    assert seen == [(99, None)]


def test_bulk_refresh_source_fallback_reuses_one_connector(monkeypatch):
    """N+1 fix: widgets sharing a connection build one connector (not one each)
    on the source-DB fallback, and it is closed once."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(
        wd, "_read_widget_from_cache",
        lambda dash_id, wid, org_id=None, user_id=None, plane=None: None,  # cache miss → source
    )

    result = FakeQueryResult(columns=["cnt"], rows=[(7,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.execute_query.return_value = result

    factory_calls = {"n": 0}

    def _get_conn(conn, db=None):
        factory_calls["n"] += 1
        return fake_connector

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection", _get_conn,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 7})

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w1"), _bulk_widget("w2")],  # same connection_id=42
    )
    # endpoint dashboard lookup, then ONE connection lookup (second widget reuses cache)
    db = _db_with_first(dashboard, FakeConnection())

    resp = _run(wd.refresh_dashboard_widgets(1, None, _user(org_id="org-1"), db))

    assert factory_calls["n"] == 1                       # one connector for both widgets
    assert fake_connector.execute_query.call_count == 2  # but each widget queried
    assert fake_connector.close.call_count == 1          # closed once, after the loop
    assert set(resp.widgets.keys()) == {"w1", "w2"}
    assert all(resp.widgets[w]["served_from"] == "source" for w in ("w1", "w2"))


def test_resolve_serving_plane_hands_over_the_request_session(monkeypatch):
    """The one line that removes the extra connection: `get_default_plane` must
    receive the caller's session. With db=None it opens its own
    (`data_plane_service.get_default_plane` → `SessionLocal()`), which is the
    connection this whole change exists to stop taking.

    Installs the module into sys.modules for the duration instead of patching an
    attribute on it: tests/services/test_resource_lifecycle.py permanently swaps a
    MagicMock in there at import time, so neither a "backend.services...." string
    patch nor a setattr on the imported object binds predictably in a combined run
    (the same pollution already fails the `test_serve_via_dataplane_*` siblings).
    """
    calls = []
    monkeypatch.setitem(
        sys.modules, "backend.services.data_plane_service",
        SimpleNamespace(
            get_default_plane=lambda scope, db=None: (calls.append(db), "plane")[1],
        ),
    )

    db = MagicMock()
    assert wd._resolve_serving_plane("org-1", "u-1", db) == "plane"
    assert calls == [db]


def test_resolve_serving_plane_returns_none_when_no_plane_is_provisioned(monkeypatch):
    """A resolution failure must degrade to "cold cache → serve from source",
    which is what the raised NoPlaneProvisionedError did before it was hoisted
    out of the per-widget read. Raising here would fail the whole refresh."""
    def _boom(scope, db=None):
        raise RuntimeError("no plane provisioned")

    monkeypatch.setitem(
        sys.modules, "backend.services.data_plane_service",
        SimpleNamespace(get_default_plane=_boom),
    )
    assert wd._resolve_serving_plane("org-1", "u-1", MagicMock()) is None


def test_bulk_refresh_does_not_retry_resolution_when_no_plane_exists(monkeypatch):
    """A failed resolution must be resolved *once*, not re-attempted per widget.

    `plane=None` is a resolved answer ("there is none"), not "unset". Conflating
    them sends every widget back through `read_widget_data_plane`'s own
    `get_default_plane`, restoring the per-widget pooled connection this change
    removes — and under lockdown re-running provision-on-miss once per widget,
    creating buckets/datasets on a read path.
    """
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    attempts = []

    def _resolve(org_id, user_id, db):
        attempts.append(db)
        return None  # nothing provisioned

    monkeypatch.setattr(wd, "_resolve_serving_plane", _resolve)

    # Real _read_widget_from_cache → real read_widget_data_plane: the retry, if
    # any, happens inside it. Count what it would fall back to.
    retries = []
    monkeypatch.setitem(
        sys.modules, "backend.services.data_plane_service",
        SimpleNamespace(
            get_default_plane=lambda scope, db=None: retries.append(db) or SimpleNamespace(
                table_exists=lambda s, t: False,
            ),
        ),
    )

    fake_connector = MagicMock()
    fake_connector.execute_query.return_value = FakeQueryResult(
        columns=["cnt"], rows=[(7,)], row_count=1,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: fake_connector,
    )

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w1"), _bulk_widget("w2"), _bulk_widget("w3")],
    )
    db = _db_with_first(dashboard, FakeConnection())

    resp = _run(wd.refresh_dashboard_widgets(1, None, _user(org_id="org-1"), db))

    assert len(attempts) == 1, f"resolved once even on miss, got {len(attempts)}"
    assert retries == [], "a None plane must not fall back to self-resolution"
    assert set(resp.widgets.keys()) == {"w1", "w2", "w3"}
    assert all(resp.widgets[w]["served_from"] == "source" for w in ("w1", "w2", "w3"))


def test_bulk_refresh_skips_plane_resolution_entirely_when_filtered(monkeypatch):
    """Filtered requests never read `_dash_*` (it holds unfiltered rows), so they
    must not resolve a plane at all — under lockdown a miss would invoke
    provision-on-miss, a bucket/dataset side effect on a request that never
    touches the cache."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    attempts = []
    monkeypatch.setattr(
        wd, "_resolve_serving_plane",
        lambda org_id, user_id, db: attempts.append(db),
    )

    fake_connector = MagicMock()
    fake_connector.execute_query.return_value = FakeQueryResult(
        columns=["cnt"], rows=[(7,)], row_count=1,
    )
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: fake_connector,
    )

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={}, widgets=[_bulk_widget("w1")],
    )
    db = _db_with_first(dashboard, FakeConnection())
    payload = wd.BulkRefreshRequest(filters=[wd.FilterParam(column="c", op="eq", value="x")])

    resp = _run(wd.refresh_dashboard_widgets(1, payload, _user(org_id="org-1"), db))

    assert attempts == [], "filtered request must not resolve a plane"
    assert resp.widgets["w1"]["served_from"] == "source"


def test_bulk_refresh_resolves_the_cache_plane_once_for_all_widgets(monkeypatch):
    """Connection accounting: the `_dash_*` cache plane resolves ONCE per bulk
    request, reusing the request's own session.

    `read_widget_data_plane` resolves its own plane when none is passed, and
    `get_default_plane` with no session opens one — so a per-widget read put a
    second pooled connection in flight on top of the one the request already
    holds, N times over. Against `DB_POOL_SIZE`+`DB_MAX_OVERFLOW` (5+5 in prod)
    a multi-widget dashboard exhausted the pool: `QueuePool limit of size 5
    overflow 5 reached, connection timed out`. Memoizing connection+connector
    (the test above) never covered this lookup.

    Asserting `is db` matters as much as the count: resolving once but with a
    fresh session would still take the extra connection.
    """
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    # Patched on `wd`, not via "backend.services.data_plane_service...":
    # tests/services/test_resource_lifecycle.py replaces that module with a
    # MagicMock in sys.modules at import time and never restores it, so a
    # string-path patch silently lands on the mock in any combined run.
    resolved_with = []
    sentinel_plane = object()

    def _resolve(org_id, user_id, db):
        resolved_with.append(db)
        return sentinel_plane

    monkeypatch.setattr(wd, "_resolve_serving_plane", _resolve)

    planes_seen = []

    def _cache_read(dash_id, wid, org_id=None, user_id=None, plane=None):
        planes_seen.append(plane)
        return FakeQueryResult(columns=["cnt"], rows=[(1,)], row_count=1)

    monkeypatch.setattr(wd, "_read_widget_from_cache", _cache_read)

    dashboard = SimpleNamespace(
        id=1, user_id="u-1", data_context={},
        widgets=[_bulk_widget("w1"), _bulk_widget("w2"), _bulk_widget("w3")],
    )
    db = _db_with_first(dashboard)

    resp = _run(wd.refresh_dashboard_widgets(1, None, _user(org_id="org-1"), db))

    assert len(resolved_with) == 1, f"one resolution per request, got {len(resolved_with)}"
    assert resolved_with[0] is db, "must reuse the request's session, not open another"
    assert len(planes_seen) == 3, "every widget still reads the cache"
    assert all(p is sentinel_plane for p in planes_seen), "all widgets share THE one plane"
    assert set(resp.widgets.keys()) == {"w1", "w2", "w3"}
    assert all(resp.widgets[w]["served_from"] == "cache" for w in ("w1", "w2", "w3"))


def test_refresh_widget_resolves_the_cache_plane_with_the_request_session(monkeypatch):
    """Single-widget path: same accounting, one widget. The plane is resolved
    with the request's session rather than `read_widget_data_plane` opening its
    own — the second of the 2-3 connections one refresh used to hold."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    resolved_with = []
    sentinel_plane = object()

    def _resolve(org_id, user_id, db):
        resolved_with.append(db)
        return sentinel_plane

    monkeypatch.setattr(wd, "_resolve_serving_plane", _resolve)

    planes_seen = []

    def _cache_read(dash_id, wid, org_id=None, user_id=None, plane=None):
        planes_seen.append(plane)
        return FakeQueryResult(columns=["cnt"], rows=[(1,)], row_count=1)

    monkeypatch.setattr(wd, "_read_widget_from_cache", _cache_read)

    db = _db_with_first(FakeDashboard(), FakeConnection())
    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
        dashboard_id=1, widget_id="kpi_1",
    )
    resp = _run(wd.refresh_widget(req, _user(org_id="org-1"), db))

    assert resolved_with == [db]
    assert planes_seen == [sentinel_plane]
    assert resp.served_from == "cache"


def test_refresh_widget_keeps_a_capped_cache_read_marked_truncated(monkeypatch):
    """The legacy cache branch hard-coded truncated=False. A table mapping never
    raises on a capped result, so the response was written through to the Redis
    result cache as complete — and that cache is keyed by SQL, not by mapping,
    so the same rows came back under a KPI mapping as a partial aggregate."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"rows": []})
    monkeypatch.setattr(wd, "_resolve_serving_plane", lambda org_id, user_id, db: object())
    monkeypatch.setattr(
        wd, "_read_widget_from_cache",
        lambda dash_id, wid, org_id=None, user_id=None, plane=None: FakeQueryResult(
            columns=["v"], rows=[(1,)], row_count=5000, truncated=True,
        ),
    )

    db = _db_with_first(FakeDashboard(), FakeConnection())
    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT v FROM orders", mapping={"type": "table"},
        dashboard_id=1, widget_id="kpi_1",
    )
    resp = _run(wd.refresh_widget(req, _user(org_id="org-1"), db))

    assert resp.served_from == "cache"
    assert resp.truncated is True


def test_bulk_refresh_applies_filters_and_skips_cache(monkeypatch):
    """With filters, the bulk endpoint must (a) NOT read the unfiltered cache and
    (b) inject the filter into the source SQL — parity with single-widget."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)

    cache_calls = {"n": 0}
    def _cache(*a, **k):
        cache_calls["n"] += 1
        return FakeQueryResult(columns=["v"], rows=[(1,)], row_count=1)
    monkeypatch.setattr(wd, "_read_widget_from_cache", _cache)

    captured = {"sql": None, "params": None}
    fake_connector = MagicMock()
    def _exec(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return FakeQueryResult(columns=["v"], rows=[(1,)], row_count=1)
    fake_connector.execute_query.side_effect = _exec
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection", lambda c, db=None: fake_connector,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda r, m: {"value": 1})

    dashboard = SimpleNamespace(id=1, user_id="u-1", data_context={}, widgets=[_bulk_widget("w1")])
    db = _db_with_first(dashboard, FakeConnection(db_type="bigquery"))

    payload = wd.BulkRefreshRequest(filters=[wd.FilterParam(column="region", op="eq", value="EMEA")])
    resp = _run(wd.refresh_dashboard_widgets(1, payload, _user(org_id="org-1"), db))

    assert cache_calls["n"] == 0                       # cache skipped under filters
    assert resp.widgets["w1"]["served_from"] == "source"
    assert "region" in captured["sql"]                 # filter injected
    assert captured["params"] == {"_f0": "EMEA"}


# ── Bootstrap policy: pg/mysql connectors both fallback correctly ──────────

def test_source_db_fallback_works_for_mysql_connection(monkeypatch):
    """MySQL widget, plane cold → source DB fallback via the connector."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    monkeypatch.setattr(wd, "_serve_widget_via_dataplane",
                         lambda req, dash, user, db: None)
    monkeypatch.setattr(wd, "_read_widget_from_cache",
                         lambda dash_id, wid, org_id, user_id, plane=None: None)

    result = FakeQueryResult(columns=["cnt"], rows=[(42,)], row_count=1)
    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.return_value = result

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: fake_connector,
    )

    def _transform(result, mapping):
        return {"value": 42}
    monkeypatch.setattr(wd, "transform_widget_data", _transform)

    # dashboard first(), connection second ()
    mysql_conn = FakeConnection(db_type="mysql")
    db = _db_with_first(FakeDashboard(), mysql_conn)

    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM orders", mapping={},
        dashboard_id=1, widget_id="kpi_1",
    )
    resp = _run(wd.refresh_widget(req, _user(org_id="org-1"), db))
    assert resp is not None
    assert resp.config["value"] == 42


def test_refresh_widget_postgres_source_repairs_ansi_quotes_for_mysql(monkeypatch):
    """Orchestration: a MySQL widget whose stored SQL uses ANSI double-quoted
    identifiers must reach the source as backtick identifiers. `normalize_sql_for`
    now repairs the quoting on the FIRST (native) attempt, so the widget renders
    without burning the bigquery/postgres transpile plans behind it."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)

    result = FakeQueryResult(columns=["amt"], rows=[(7,)], row_count=1)

    def _exec(sql, params=None):
        # The source only accepts MySQL-native backtick identifiers; ANSI
        # double-quotes are rejected.
        if "`amt`" in sql:
            return result
        raise Exception(f"unknown identifier quoting: {sql}")

    fake_connector = MagicMock()
    fake_connector.__enter__ = lambda self: self
    fake_connector.__exit__ = lambda *a: None
    fake_connector.execute_query.side_effect = _exec

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: fake_connector,
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 7})

    db = _db_with_first(FakeConnection(db_type="mysql"))
    req = wd.WidgetRefreshRequest(
        connection_id=42, sql='SELECT "amt" FROM sales', mapping={},
    )
    resp = _run(wd.refresh_widget(req, _user(), db))

    assert resp is not None
    assert resp.row_count == 1
    assert resp.config == {"value": 7}
    # One attempt, already correctly quoted. Before normalization this needed
    # three (native + bigquery + postgres-repair).
    assert fake_connector.execute_query.call_count == 1
    assert "`amt`" in fake_connector.execute_query.call_args_list[-1].args[0]


def test_refresh_widget_plane_backed_connector_reports_data_plane(monkeypatch):
    """A plane-backed connector (migrated sqlite, CSV dataset) reads Parquet, so
    the response must say `data_plane` — MagicMock connectors stay `source`."""
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)

    class FakePlaneConnector:
        serves_from_plane = True

        def execute_query(self, sql, params=None):
            return FakeQueryResult(columns=["cnt"], rows=[(3,)], row_count=1)

        def close(self):
            pass

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: FakePlaneConnector(),
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 3})

    db = _db_with_first(FakeConnection(db_type="dataset"))
    req = wd.WidgetRefreshRequest(
        connection_id=42, sql="SELECT COUNT(*) FROM csv_42", mapping={},
    )
    resp = _run(wd.refresh_widget(req, _user(), db))

    assert resp.served_from == "data_plane"

    # Pin the real core connector too — the fake above only covers the contract.
    from backend.connectors.data_plane import DataPlaneConnector
    assert DataPlaneConnector.serves_from_plane is True


# ── Request-scoped dataplane-miss memo ───────────────────────────────────────
#
# A cold/absent Parquet glob is discovered by *attempting* the read — a full GCS
# round-trip (~3-4s). On the live run four widgets on the same table each paid it
# (~14.3s of a ~20s dashboard load). Probe once per (connection, tables).


def test_plane_miss_key_groups_widgets_on_the_same_tables():
    a = wd._plane_miss_key(42, "SELECT role, COUNT(*) FROM csv_104 GROUP BY role")
    b = wd._plane_miss_key(42, "SELECT salary FROM csv_104 WHERE salary > 0")
    assert a == b


def test_plane_miss_key_separates_different_tables_and_connections():
    base = wd._plane_miss_key(42, "SELECT * FROM csv_104")
    assert base != wd._plane_miss_key(42, "SELECT * FROM csv_999")
    assert base != wd._plane_miss_key(43, "SELECT * FROM csv_104")


def test_plane_miss_key_falls_back_to_the_sql_when_unparseable():
    a = wd._plane_miss_key(42, "not sql ((")
    b = wd._plane_miss_key(42, "also not sql ((")
    assert a != b  # never collapse two queries we could not read


def _memo_db(dashboard):
    """MagicMock db for refresh_dashboard_widgets: no sample connections."""
    db = MagicMock()
    q = db.query.return_value
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.first.return_value = dashboard
    q.all.return_value = []
    return db


def _memo_dashboard(widgets):
    return SimpleNamespace(id=1, user_id="u-1", org_id=None,
                           data_context={}, widgets=widgets)


def _memo_widget(wid, sql, connection_id=42):
    return {
        "id": wid,
        "widget": {"type": "kpi", "config": {}},
        "dataSource": {"connectionId": connection_id, "sql": sql, "mapping": {"type": "kpi"}},
    }


def _setup_bulk(monkeypatch, dashboard):
    """Patch the bulk-refresh collaborators; returns the probe-call log."""
    monkeypatch.setattr(
        "backend.api.dashboards._dashboard_visible_to",
        lambda q, user, db: q,
    )
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: True)
    monkeypatch.setattr(wd, "_widget_cache_enabled", lambda org_id: False)
    # raising=False: another suite stubs out data_plane_service, so the real
    # attribute is not always there when the whole suite runs.
    monkeypatch.setattr(
        "backend.services.data_plane_service.get_gcs_duckdb_reader",
        lambda scope, db: None,
        raising=False,
    )
    monkeypatch.setattr(wd, "_read_widget_from_cache", lambda *a, **k: None)
    # Source fallback short-circuits into a per-widget {"error": …} result.
    monkeypatch.setattr(wd, "_readable_connection", lambda *a, **k: None)

    probes = []

    def _probe(request, dash, user, db, reader=None):
        probes.append(request.widget_id)
        return None

    monkeypatch.setattr(wd, "_serve_widget_via_dataplane", _probe)
    return probes


def test_bulk_refresh_probes_a_failing_scope_once(monkeypatch):
    dashboard = _memo_dashboard([
        _memo_widget("w1", "SELECT role FROM csv_104"),
        _memo_widget("w2", "SELECT salary FROM csv_104"),
        _memo_widget("w3", "SELECT COUNT(*) FROM csv_104"),
    ])
    probes = _setup_bulk(monkeypatch, dashboard)

    _run(wd.refresh_dashboard_widgets(1, None, _user(), _memo_db(dashboard)))

    assert probes == ["w1"]


def test_bulk_refresh_still_probes_a_different_table(monkeypatch):
    dashboard = _memo_dashboard([
        _memo_widget("w1", "SELECT role FROM csv_104"),
        _memo_widget("w2", "SELECT * FROM csv_999"),
    ])
    probes = _setup_bulk(monkeypatch, dashboard)

    _run(wd.refresh_dashboard_widgets(1, None, _user(), _memo_db(dashboard)))

    assert probes == ["w1", "w2"]


def test_bulk_refresh_memo_does_not_leak_across_requests(monkeypatch):
    dashboard = _memo_dashboard([_memo_widget("w1", "SELECT role FROM csv_104")])
    probes = _setup_bulk(monkeypatch, dashboard)

    _run(wd.refresh_dashboard_widgets(1, None, _user(), _memo_db(dashboard)))
    _run(wd.refresh_dashboard_widgets(1, None, _user(), _memo_db(dashboard)))

    assert probes == ["w1", "w1"]


def test_bulk_refresh_serves_every_widget_when_the_probe_succeeds(monkeypatch):
    dashboard = _memo_dashboard([
        _memo_widget("w1", "SELECT role FROM csv_104"),
        _memo_widget("w2", "SELECT salary FROM csv_104"),
    ])
    probes = _setup_bulk(monkeypatch, dashboard)

    def _ok(request, dash, user, db, reader=None):
        probes.append(request.widget_id)
        return SimpleNamespace(config={"value": 1}, served_from="data_plane")

    monkeypatch.setattr(wd, "_serve_widget_via_dataplane", _ok)
    monkeypatch.setattr(wd, "_widget_cache_store", lambda *a, **k: None)

    resp = _run(wd.refresh_dashboard_widgets(1, None, _user(), _memo_db(dashboard)))

    assert probes == ["w1", "w2"]
    assert resp.widgets["w1"]["served_from"] == "data_plane"


def test_bulk_refresh_does_not_block_the_event_loop(monkeypatch):
    """The serving ladder is fully synchronous. Run inline it stalls the loop for
    the whole dashboard (~10s per filter change on dashboard 39, per
    `loop_watchdog`) and starves every other request — the 2026-07-23
    liveness-kill shape. `refresh_widget` was moved to a worker thread then; this
    pins that the bulk endpoint stays there too.
    """
    dashboard = _memo_dashboard([_memo_widget("w1", "SELECT role FROM csv_104")])
    _setup_bulk(monkeypatch, dashboard)

    import time

    def _slow(request, dash, user, db, reader=None):
        time.sleep(0.3)  # blocking, as every real serving path is
        return SimpleNamespace(config={"value": 1}, served_from="data_plane")

    monkeypatch.setattr(wd, "_serve_widget_via_dataplane", _slow)
    monkeypatch.setattr(wd, "_widget_cache_store", lambda *a, **k: None)

    order = []

    async def _bulk():
        await wd.refresh_dashboard_widgets(1, None, _user(), _memo_db(dashboard))
        order.append("bulk")

    async def _other():
        await asyncio.sleep(0.05)
        order.append("other")

    async def _both():
        await asyncio.gather(_bulk(), _other())

    asyncio.run(_both())

    # Inline, the 0.3s sleep would pin the loop and "bulk" would land first.
    assert order == ["other", "bulk"]


# ── Serve-path SQL normalization ─────────────────────────────────────────────
#
# Widgets persisted with ANSI `"col"` quoting are string literals on BigQuery,
# and a column named `left` is a syntax error everywhere. The transpile ladder
# below can't repair either for dataset/plane connections — their db_type isn't
# a sqlglot dialect, so every non-native plan raises. Normalize the native try.

_RESERVED = 'SELECT c."role" AS role, c."left" AS left FROM csv_104 c'


def test_source_fallback_normalizes_the_native_attempt(monkeypatch):
    monkeypatch.setattr(wd, "_duckdb_serving_enabled", lambda org_id: False)
    monkeypatch.setattr(wd, "_read_widget_from_cache", lambda *a, **k: None)
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True, raising=False)

    seen = []

    class _Recorder:
        def execute_query(self, sql, params=None):
            seen.append(sql)
            return FakeQueryResult(columns=["role"], rows=[("eng",)], row_count=1)

        def close(self):
            pass

    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection", lambda conn, db=None: _Recorder(),
    )
    monkeypatch.setattr(wd, "transform_widget_data", lambda result, mapping: {"value": 1})

    db = _db_with_first(FakeConnection(db_type="dataset"))
    req = wd.WidgetRefreshRequest(connection_id=42, sql=_RESERVED, mapping={})
    _run(wd.refresh_widget(req, _user(), db))

    assert seen, "connector was never called"
    assert "`role`" in seen[0]        # ANSI quotes would be a string literal on BQ
    assert "`left`" in seen[0]        # reserved word now quoted


# NOTE: the DuckDB branch of `_serve_widget_via_dataplane` also normalizes
# (`normalize_sql_for(base_sql, "duckdb")`, quoting reserved-word identifiers).
# It is not covered end-to-end here: every test that drives that branch resolves
# a different `data_plane_service` module object than monkeypatch patches when
# the whole suite runs, which is why its siblings above are in the known-failing
# baseline. The rewrite itself is covered by
# backend/tests/services/test_schema_utils_normalize.py.
