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

    def query(self, scope, sql, params=None):
        self.calls.append((sql, params))
        return self._result

    def close(self):
        pass


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
    db.query.return_value.filter.return_value.first.return_value = None
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
    # Cache table not warmed yet → reader raises → None → fall back.
    class _Raiser:
        def query(self, *a, **k):
            raise RuntimeError("no files matched gs://…/_dash_5__w1/dt=*")
        def close(self):
            pass

    monkeypatch.setattr(dps, "get_plane_for_connection", lambda c: (object(), OwnerScope("org", "o1")))
    monkeypatch.setattr(dps, "get_gcs_duckdb_reader", lambda scope, db: _Raiser())
    req = _request("SELECT region FROM csv_1", dashboard_id=5)
    assert _serve_widget_via_dataplane(req, SimpleNamespace(data_context=None), current_user, db_with_connection) is None
