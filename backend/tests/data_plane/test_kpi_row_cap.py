"""The row cap is enforced by the query engine, below the widget transform.

`settings.max_query_rows` clamps in every source connector (`connectors/base.py`)
and in the shared DuckDB runner, so by the time `transform_kpi` runs, a KPI over
raw rows has already lost the tail. These tests drive the real runner rather than
patching it out, which is what made the earlier "KPI is not capped" cover vacuous.
"""
from __future__ import annotations

import duckdb
import pytest
from unittest.mock import MagicMock

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


def test_warm_cache_read_reports_the_cap_as_truncation(monkeypatch):
    """The bake writes the engine's capped rows and no truncation marker.

    `materialize_dashboard` stores `result.rows` as Parquet; nothing carries
    `truncated` alongside it, and the cloud plane's `drop_table` is a no-op, so
    an already-baked capped table cannot be evicted either. The row count is
    therefore the only evidence left — a cache sitting exactly on the cap is the
    prefix of a larger result, and summing it client-side is the wrong-number
    failure this branch exists to remove.
    """
    from backend.connectors.base import QueryResult
    from backend.services import dashboard_cache

    monkeypatch.setattr(settings, "max_query_rows", 3)

    plane = MagicMock()
    plane.read_table.return_value = QueryResult(
        columns=["v"], rows=[(1,), (2,), (3,)], row_count=3, execution_time_ms=1.0,
    )
    data = dashboard_cache.read_widget_data_plane(7, "w1", "org-1", "u-1", plane=plane)
    assert data["truncated"] is True

    # One row below the cap is a complete result and stays aggregatable.
    plane.read_table.return_value = QueryResult(
        columns=["v"], rows=[(1,), (2,)], row_count=2, execution_time_ms=1.0,
    )
    assert dashboard_cache.read_widget_data_plane(
        7, "w1", "org-1", "u-1", plane=plane,
    )["truncated"] is False


def test_capped_cache_reaches_transform_kpi_as_truncated(monkeypatch):
    """`_read_widget_from_cache` must carry the flag, or the guard never runs."""
    from backend.api import widget_data as wd

    monkeypatch.setattr(settings, "max_query_rows", 3)
    monkeypatch.setattr(
        "backend.services.dashboard_cache.read_widget_data_plane",
        lambda dash_id, wid, org_id, user_id, **kw: {
            "columns": ["v"], "rows": [(1,), (2,), (3,)], "row_count": 3,
            "truncated": True,
        },
    )

    result = wd._read_widget_from_cache(7, "w1", "org-1", "u-1", plane=MagicMock())
    assert result.truncated is True
    with pytest.raises(ValueError, match="truncated"):
        transform_kpi(result, {"valueColumn": "v", "aggregation": "sum"})


def test_flag_capped_cache_marks_a_duckdb_warm_read(monkeypatch):
    """The DuckDB-over-GCS warm read goes straight to the reader, bypassing
    `read_widget_data_plane`, so it needs the same inference."""
    from backend.api import widget_data as wd
    from backend.connectors.base import QueryResult

    monkeypatch.setattr(settings, "max_query_rows", 3)
    at_cap = QueryResult(columns=["v"], rows=[(1,), (2,), (3,)], row_count=3,
                         execution_time_ms=1.0)
    assert wd._flag_capped_cache(at_cap).truncated is True

    below = QueryResult(columns=["v"], rows=[(1,)], row_count=1, execution_time_ms=1.0)
    assert wd._flag_capped_cache(below).truncated is False
    assert wd._flag_capped_cache(None) is None
