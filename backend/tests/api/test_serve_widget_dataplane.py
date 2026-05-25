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


def _request(sql, filters=None):
    return WidgetRefreshRequest(
        connection_id=1,
        sql=sql,
        mapping={"type": "table", "columnConfig": [{"column": "region"}, {"column": "total"}]},
        filters=filters,
        widget_id="w1",
    )


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
