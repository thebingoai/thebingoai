"""Tests for GAP-3: landing dbt outputs in the DataPlane Parquet lake (dev path).

Lives under tests/data_plane (real imports) rather than tests/transforms, whose
conftest stubs SQLAlchemy/models and is incompatible with the real plane I/O
exercised here.
"""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import duckdb
import pytest

import backend.services.data_plane_service as dps
from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.transforms.materialize import materialize_dbt_model_to_dataplane


@pytest.fixture
def scope():
    return OwnerScope("org", "o1")


@pytest.fixture
def plane(tmp_path):
    p = LocalFilesystemDataPlane(root_path=str(tmp_path))
    yield p
    p.close()


def _make_dbt_model(plane, scope, model):
    """Create a per-scope dbt.duckdb with a materialized model table."""
    scope_root = os.path.join(plane._root, scope.as_path())
    os.makedirs(scope_root, exist_ok=True)
    con = duckdb.connect(os.path.join(scope_root, "dbt.duckdb"))
    con.execute(f'CREATE TABLE "{model}"(region VARCHAR, amount INTEGER)')
    con.execute(f"INSERT INTO \"{model}\" VALUES ('EMEA', 10), ('APAC', 7)")
    con.close()


def test_read_dbt_model_into_arrow(plane, scope):
    _make_dbt_model(plane, scope, "stg_sales")
    arrow = plane.read_dbt_model(scope, "stg_sales")
    assert arrow.num_rows == 2
    assert set(arrow.column_names) == {"region", "amount"}


def test_read_dbt_model_missing_store_raises(plane, scope):
    with pytest.raises(FileNotFoundError):
        plane.read_dbt_model(scope, "nope")


def test_materialize_table_model_to_parquet(plane, scope, monkeypatch):
    _make_dbt_model(plane, scope, "stg_sales")
    monkeypatch.setattr(dps, "get_default_plane", lambda s, db=None: plane)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        materialization="table", unique_key=None
    )

    assert materialize_dbt_model_to_dataplane(scope, "stg_sales", db=db) is True
    # Now servable from the lake like any pipeline/dataset table.
    assert plane.table_exists(scope, "stg_sales")
    res = plane.query(scope, "SELECT count(*) AS n FROM stg_sales")
    assert res.rows[0][0] == 2


def test_materialize_skips_view_model(plane, scope, monkeypatch):
    monkeypatch.setattr(dps, "get_default_plane", lambda s, db=None: plane)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        materialization="view", unique_key=None
    )
    assert materialize_dbt_model_to_dataplane(scope, "v_model", db=db) is False
    assert not plane.table_exists(scope, "v_model")
