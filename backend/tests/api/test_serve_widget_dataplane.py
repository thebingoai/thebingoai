"""Tests for the DuckDB-over-DataPlane widget serving path (Phase 1, 1c/1d/1e).

Exercises `_serve_widget_via_dataplane` against a real LocalFilesystemDataPlane
on a temp dir, patching `get_plane_for_connection` so the lockdown guard in
`_instantiate` is bypassed (this container runs DISABLE_LOCAL_DATA_PLANE=true).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pyarrow as pa
import pytest

import backend.services.data_plane_service as dps
from backend.api.widget_data import _serve_widget_via_dataplane
from backend.connectors.base import QueryResult
from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.schemas.widget_data import FilterParam, WidgetRefreshRequest


@pytest.fixture
def scope():
    return OwnerScope("user", "u1")


@pytest.fixture
def plane(tmp_path):
    p = LocalFilesystemDataPlane(root_path=str(tmp_path))
    yield p
    p.close()


@pytest.fixture
def current_user():
    return SimpleNamespace(id="u1", org_id="o1")


@pytest.fixture(autouse=True)
def _gate_open(monkeypatch):
    """Default the GAP-10 cutover gate open so serving-mechanics tests proceed.

    The dedicated gate test overrides this.
    """
    import backend.migration.dialect_migration as dm
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda dashboard_id, db: True)


@pytest.fixture
def db_with_connection():
    """Fake Session whose connection lookup returns a truthy connection."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=1, user_id="u1", org_id=None
    )
    return db


def _write_sales(plane, scope):
    plane.write_parquet(
        scope,
        "csv_1",
        pa.table({
            "region": pa.array(["EMEA", "EMEA", "APAC"]),
            "amount": pa.array([10, 5, 7], type=pa.int64()),
        }),
    )


def _request(sql, filters=None, dashboard_id=None):
    return WidgetRefreshRequest(
        connection_id=1,
        sql=sql,
        mapping={"type": "table", "columnConfig": [{"column": "region"}, {"column": "total"}]},
        filters=filters,
        widget_id="w1",
        dashboard_id=dashboard_id,
    )


class _FakeReader:
    """Stand-in for GCSDuckDBReader capturing the SQL/params it's asked to run."""

    def __init__(self, result):
        self._result = result
        self.calls = []
        self.closed = False

    def query(self, scope, sql, params=None):
        self.calls.append((sql, params))
        return self._result

    def close(self):
        self.closed = True


def _qr(columns, rows):
    return QueryResult(columns=columns, rows=rows, row_count=len(rows), execution_time_ms=1.0, truncated=False)


def test_serves_unfiltered_from_dataplane(monkeypatch, plane, scope, current_user, db_with_connection):
    _write_sales(plane, scope)
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))

    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region")
    resp = _serve_widget_via_dataplane(req, None, current_user, db_with_connection)

    assert resp is not None
    assert resp.truncated is False
    totals = {r["region"]: r["total"] for r in resp.config["rows"]}
    assert totals == {"EMEA": 15, "APAC": 7}


def test_serves_filtered_in_duckdb_dialect(monkeypatch, plane, scope, current_user, db_with_connection):
    _write_sales(plane, scope)
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))

    req = _request(
        "SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region",
        filters=[FilterParam(column="region", op="eq", value="EMEA")],
    )
    resp = _serve_widget_via_dataplane(req, None, current_user, db_with_connection)

    assert resp is not None
    totals = {r["region"]: r["total"] for r in resp.config["rows"]}
    assert totals == {"EMEA": 15}  # APAC filtered out


def test_cold_source_returns_none(monkeypatch, plane, scope, current_user, db_with_connection):
    # Table never written → fall back to source DB (None).
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))
    req = _request("SELECT region FROM csv_1")
    assert _serve_widget_via_dataplane(req, None, current_user, db_with_connection) is None


def test_non_local_plane_returns_none(monkeypatch, scope, current_user, db_with_connection):
    # Prod BigQueryGCSPlane serving is Phase 2 — Phase 1 only handles local-fs.
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (object(), scope))
    req = _request("SELECT region FROM csv_1")
    assert _serve_widget_via_dataplane(req, None, current_user, db_with_connection) is None


def test_missing_connection_returns_none(monkeypatch, current_user):
    db = MagicMock()
    # Self-returning filter: _readable_connection issues a second, shared-sample
    # query on the ownership miss, so both chains must resolve to None.
    q = db.query.return_value
    q.filter.return_value = q
    q.first.return_value = None
    req = _request("SELECT region FROM csv_1")
    assert _serve_widget_via_dataplane(req, None, current_user, db) is None


# --- Prod branch: BigQueryGCSPlane via the DuckDB-over-GCS reader -----------

def test_prod_unfiltered_reads_warm_cache(monkeypatch, current_user, db_with_connection):
    reader = _FakeReader(_qr(["region", "total"], [("EMEA", 15)]))
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: reader)

    dashboard = SimpleNamespace(data_context=None)
    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region", dashboard_id=5)
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db_with_connection)

    assert resp is not None
    # Unfiltered prod read must hit the warm _dash_* cache, not run the full SQL.
    assert reader.calls == [('SELECT * FROM "_dash_5__w1"', None)]


def test_supplied_reader_reused_and_not_closed(monkeypatch, current_user, db_with_connection):
    """Bulk refresh passes one shared reader for the whole dashboard: the serve
    must reuse it and must NOT close it (caller owns the lifecycle) nor build
    its own via the factory."""
    reader = _FakeReader(_qr(["region", "total"], [("EMEA", 15)]))
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))

    def _boom(scope, db):
        raise AssertionError("must not create a reader when one is supplied")
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", _boom)

    dashboard = SimpleNamespace(data_context=None)
    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region", dashboard_id=5)
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db_with_connection, reader=reader)

    assert resp is not None
    assert reader.calls  # the supplied reader served the read
    assert reader.closed is False  # caller owns lifecycle — not closed here


def test_owned_reader_is_closed(monkeypatch, current_user, db_with_connection):
    """Single-widget path (no reader supplied) builds its own reader and closes
    it in the finally."""
    reader = _FakeReader(_qr(["region", "total"], [("EMEA", 15)]))
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: reader)

    dashboard = SimpleNamespace(data_context=None)
    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region", dashboard_id=5)
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db_with_connection)

    assert resp is not None
    assert reader.closed is True  # owns_reader → closed


def test_prod_filtered_runs_live_injected(monkeypatch, current_user, db_with_connection):
    reader = _FakeReader(_qr(["region", "total"], [("EMEA", 15)]))
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: reader)

    dashboard = SimpleNamespace(data_context=None)
    req = _request(
        "SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region",
        filters=[FilterParam(column="region", op="eq", value="EMEA")],
        dashboard_id=5,
    )
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db_with_connection)

    assert resp is not None
    sql, params = reader.calls[0]
    assert "$_f0" in sql and params == {"_f0": "EMEA"}  # filtered → live injected SQL


# --- served_from provenance flag (Parquet badge on widget) ------------------

def test_local_serve_marks_response_data_plane(monkeypatch, plane, scope, current_user, db_with_connection):
    """Local dev path: a successful DuckDB-over-Parquet serve must tag the
    response as `served_from='data_plane'` so the frontend renders the
    "Parquet • synced X ago" badge instead of the plain age stamp.
    """
    _write_sales(plane, scope)
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))

    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region")
    resp = _serve_widget_via_dataplane(req, None, current_user, db_with_connection)

    assert resp is not None
    assert resp.served_from == "data_plane"


def test_prod_serve_marks_response_data_plane(monkeypatch, current_user, db_with_connection):
    """Prod GCS-DuckDB path also tags `served_from='data_plane'`."""
    reader = _FakeReader(_qr(["region", "total"], [("EMEA", 15)]))
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: reader)

    dashboard = SimpleNamespace(data_context=None)
    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region", dashboard_id=5)
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db_with_connection)

    assert resp is not None
    assert resp.served_from == "data_plane"


# --- Bootstrap-fallback ("not-ready policy") for pg/mysql ------------------


def _pipeline(*, target_table="pg_demo__orders", source_tables=("orders",), first_ingest_done=False):
    return SimpleNamespace(
        target_table=target_table,
        extraction_config={"tables": list(source_tables)},
        first_ingest_done=first_ingest_done,
    )


def _db_with_pipelines(connection_obj, pipelines):
    """Fake Session whose `query(DatabaseConnection)` returns *connection_obj*
    and `query(Pipeline)` returns *pipelines*."""
    db = MagicMock()

    def query(model):
        q = MagicMock()
        if getattr(model, "__name__", "") == "Pipeline":
            q.filter.return_value.all.return_value = pipelines
        else:
            q.filter.return_value.first.return_value = connection_obj
        return q

    db.query = query
    return db


def test_bootstrap_fallback_when_first_ingest_not_done(monkeypatch, plane, scope, current_user):
    """No Parquet partition yet, first_ingest_done=False → return None so the
    caller's legacy source-DB fallback runs (one live query allowed)."""
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))
    conn_obj = SimpleNamespace(id=1, user_id="u1", org_id=None, db_type="postgres")
    db = _db_with_pipelines(conn_obj, [_pipeline(first_ingest_done=False)])

    req = _request("SELECT * FROM orders")
    resp = _serve_widget_via_dataplane(req, None, current_user, db)
    # plane.table_exists is False (we never wrote `orders`) AND first_ingest_done
    # is False → bootstrap fallback path returns None.
    assert resp is None


def test_503_after_first_ingest_done_when_plane_missing(monkeypatch, plane, scope, current_user):
    """Pipeline reports first ingest finished but Parquet is missing — refuse to
    re-hammer the source, raise HTTPException(503, code=plane_table_missing)."""
    from fastapi import HTTPException
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))
    conn_obj = SimpleNamespace(id=1, user_id="u1", org_id=None, db_type="postgres")
    db = _db_with_pipelines(conn_obj, [_pipeline(first_ingest_done=True)])

    req = _request("SELECT * FROM orders")
    with pytest.raises(HTTPException) as exc:
        _serve_widget_via_dataplane(req, None, current_user, db)
    assert exc.value.status_code == 503
    assert exc.value.detail.get("code") == "plane_table_missing"


def test_bootstrap_fallback_ignores_unrelated_pipelines(monkeypatch, plane, scope, current_user):
    """A done pipeline for a DIFFERENT table must not trigger the 503 for
    the queried table — only matching pipelines gate the policy."""
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda conn: (plane, scope))
    conn_obj = SimpleNamespace(id=1, user_id="u1", org_id=None, db_type="postgres")
    db = _db_with_pipelines(
        conn_obj,
        [_pipeline(target_table="pg_demo__users", source_tables=("users",), first_ingest_done=True)],
    )

    req = _request("SELECT * FROM orders")
    resp = _serve_widget_via_dataplane(req, None, current_user, db)
    assert resp is None  # falls through to source DB


def test_prod_reader_none_falls_back(monkeypatch, current_user, db_with_connection):
    # residency-locked / customer / no-HMAC plane → factory returns None → BQ fallback.
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: None)
    req = _request("SELECT region FROM csv_1", dashboard_id=5)
    assert _serve_widget_via_dataplane(req, SimpleNamespace(data_context=None), current_user, db_with_connection) is None


def test_gate_blocks_unmigrated_dashboard(monkeypatch, plane, scope, current_user, db_with_connection):
    # Dashboard not yet journaled DuckDB → gate returns None → BQ/source fallback,
    # even though the source Parquet exists and the plane is local.
    import backend.migration.dialect_migration as dm
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda dashboard_id, db: False)
    _write_sales(plane, scope)
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (plane, scope))
    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region", dashboard_id=5)
    assert _serve_widget_via_dataplane(req, None, current_user, db_with_connection) is None


def test_prod_cold_cache_falls_back(monkeypatch, current_user, db_with_connection):
    # Reader fails on BOTH the _dash_* cache read and the live fallback read →
    # None → source-DB fallback.
    class _Raiser:
        def query(self, *a, **k):
            raise RuntimeError("no files matched gs://…/_dash_5__w1/dt=*")
        def close(self):
            pass

    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: _Raiser())
    req = _request("SELECT region FROM csv_1", dashboard_id=5)
    assert _serve_widget_via_dataplane(req, SimpleNamespace(data_context=None), current_user, db_with_connection) is None


def test_prod_unfiltered_cold_cache_serves_live(monkeypatch, current_user, db_with_connection):
    # Cold _dash_* cache but a healthy reader → serve live over the source
    # Parquet (cache read raises, live base_sql read succeeds) instead of None.
    class _ColdThenLive:
        def __init__(self, result):
            self._r = result
            self.calls = []

        def query(self, scope, sql, params=None):
            self.calls.append(sql)
            if sql.startswith('SELECT * FROM "_dash_'):
                raise RuntimeError("cold cache")
            return self._r

        def close(self):
            pass

    reader = _ColdThenLive(_qr(["region", "total"], [("EMEA", 15)]))
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: reader)

    dashboard = SimpleNamespace(data_context=None)
    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region", dashboard_id=5)
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db_with_connection)

    assert resp is not None
    assert {r["region"]: r["total"] for r in resp.config["rows"]} == {"EMEA": 15}
    # cache tried first, then the live source SQL
    assert reader.calls[0].startswith('SELECT * FROM "_dash_5__w1"')
    assert any("csv_1" in c for c in reader.calls[1:])


def test_serve_rewrites_source_table_to_plane(monkeypatch, plane, scope, current_user):
    # Widget SQL references the SOURCE table `csv_1`; its Pipeline materialized
    # it on the plane as `acme__csv_1`. The data exists only under the plane
    # name, so serving must rewrite the ref or it returns None.
    plane.write_parquet(scope, "acme__csv_1", pa.table({
        "region": pa.array(["EMEA", "EMEA", "APAC"]),
        "amount": pa.array([10, 5, 7], type=pa.int64()),
    }))

    db = MagicMock()
    chain = db.query.return_value.filter.return_value
    chain.order_by.return_value = chain  # plane_table_map orders enabled-first
    chain.first.return_value = SimpleNamespace(id=1, user_id="u1", org_id=None)
    chain.all.return_value = [
        SimpleNamespace(extraction_config={"tables": ["csv_1"]}, target_table="acme__csv_1"),
    ]
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (plane, scope))

    req = _request("SELECT region, SUM(amount) AS total FROM csv_1 GROUP BY region")
    resp = _serve_widget_via_dataplane(req, None, current_user, db)

    assert resp is not None
    assert {r["region"]: r["total"] for r in resp.config["rows"]} == {"EMEA": 15, "APAC": 7}


def test_serve_no_pipeline_no_rewrite_cold(monkeypatch, plane, scope, current_user, db_with_connection):
    # No pipeline for the connection → empty map → SQL unchanged → the source
    # table isn't on the plane → cold → None (source-DB fallback).
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (plane, scope))
    req = _request("SELECT region FROM csv_1")
    assert _serve_widget_via_dataplane(req, None, current_user, db_with_connection) is None


def test_filter_injects_inside_the_aggregate_over_a_materialized_table(monkeypatch, plane, scope, current_user):
    """The plane path rewrites `csv_1` → `acme__csv_1` BEFORE injecting filters,
    while the dashboard context still describes `csv_1`. Untranslated, the scope
    picker finds no columns for any table in the rewritten AST, concludes no
    scope covers the filter and every filtered read on a pipeline-backed
    connection degrades to the subquery wrap — which, over an aggregate, filters
    on a column the outer projection doesn't carry."""
    plane.write_parquet(scope, "acme__csv_1", pa.table({
        "region": pa.array(["EMEA", "EMEA", "APAC"]),
        "amount": pa.array([10, 5, 7], type=pa.int64()),
    }))

    db = MagicMock()
    chain = db.query.return_value.filter.return_value
    chain.order_by.return_value = chain
    chain.first.return_value = SimpleNamespace(id=1, user_id="u1", org_id=None)
    chain.all.return_value = [
        SimpleNamespace(extraction_config={"tables": ["csv_1"]}, target_table="acme__csv_1"),
    ]
    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (plane, scope))

    import backend.api.widget_data as wd

    def _boom(*a, **k):
        raise AssertionError("fell back to the subquery wrap instead of the AST path")

    monkeypatch.setattr(wd, "_wrap_subquery_fallback", _boom)

    dashboard = SimpleNamespace(
        id=7,
        data_context={
            "sources": {"csv_1": {"columns": ["region", "amount"]}},
            "dimensions": {"region": {"column": "region", "sources": ["csv_1"]}},
        },
    )
    req = WidgetRefreshRequest(
        connection_id=1,
        sql="SELECT SUM(amount) AS total FROM csv_1",
        mapping={"type": "table", "columnConfig": [{"column": "total"}]},
        filters=[FilterParam(column="region", op="eq", value="EMEA")],
        widget_id="w1",
        dashboard_id=7,
    )
    resp = _serve_widget_via_dataplane(req, dashboard, current_user, db)

    assert resp is not None
    assert resp.config["rows"] == [{"total": 15}]  # 10 + 5, APAC excluded
