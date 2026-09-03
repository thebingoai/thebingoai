"""The row cap is enforced by the query engine, below the widget transform.

`settings.max_query_rows` clamps in every source connector (`connectors/base.py`)
and in the shared DuckDB runner, so by the time `transform_kpi` runs, a KPI over
raw rows has already lost the tail. These tests drive the real runner rather than
patching it out, which is what made the earlier "KPI is not capped" cover vacuous.
"""
from __future__ import annotations

import duckdb
import pytest

from backend.config import settings
from backend.data_plane.duckdb_exec import run_duckdb_query
from backend.services.widget_transform import transform_kpi


def test_runner_flags_truncation_and_kpi_refuses_to_aggregate(monkeypatch):
    monkeypatch.setattr(settings, "max_query_rows", 3)
    conn = duckdb.connect()
    try:
        result = run_duckdb_query(conn, "SELECT * FROM range(10) t(v)")
    finally:
        conn.close()

    assert result.truncated is True
    assert result.row_count == 3

    with pytest.raises(ValueError, match="truncated"):
        transform_kpi(result, {"valueColumn": "v", "aggregation": "sum"})


def test_untruncated_result_aggregates_normally(monkeypatch):
    monkeypatch.setattr(settings, "max_query_rows", 100)
    conn = duckdb.connect()
    try:
        result = run_duckdb_query(conn, "SELECT * FROM range(4) t(v)")
    finally:
        conn.close()

    assert result.truncated is False
    assert transform_kpi(result, {"valueColumn": "v", "aggregation": "sum"})["value"] == 6
