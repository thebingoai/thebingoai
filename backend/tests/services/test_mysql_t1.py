"""Unit tests for MySQL auto-scheduled incremental/full pipelines.

Covers:
  - SqlExtractionConfig new fields + the dlt incremental cursor wiring.
  - _detect_snapshot_date_column heuristic.
  - _apply_mysql_t1_schedule: incremental (with cursor) when a date col is
    detected, else full snapshot. Always sets cron + next_run_at.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import backend.connectors.sql_dlt as sql_dlt
import backend.services.template_materializer as tm
from backend.connectors.sql_dlt import SqlExtractionConfig, sql_dlt_source


# ── SqlExtractionConfig + dlt incremental wiring ─────────────────────────────

def test_extraction_config_defaults():
    cfg = SqlExtractionConfig(tables=["orders"])
    assert cfg.incremental_key is None
    assert cfg.initial_value is None


def _conn():
    return SimpleNamespace(username="u", password="p", host="h", port=3306, database="shop")


def _capture_source(monkeypatch, fake_src):
    captured = {}
    import dlt.sources.sql_database as m
    monkeypatch.setattr(m, "sql_database", lambda **kw: captured.update(kw) or fake_src)
    return captured


def test_sql_dlt_source_no_incremental_passthrough(monkeypatch):
    fake_resource = MagicMock()
    fake_src = SimpleNamespace(resources={"orders": fake_resource})
    _capture_source(monkeypatch, fake_src)
    sql_dlt_source("mysql+pymysql", _conn(), {"tables": ["orders"]})
    fake_resource.apply_hints.assert_not_called()


def test_sql_dlt_source_applies_incremental_cursor(monkeypatch):
    """Cursor is applied with an `end_value` of today 00:00 UTC even when no
    `initial_value` is provided. dlt requires `initial_value` whenever
    `end_value` is set, so a 1900-01-01 UTC sentinel is used to represent
    "unbounded lower" while still honouring the same-day exclusion."""
    from datetime import datetime, timezone

    fake_resource = MagicMock()
    fake_src = SimpleNamespace(resources={"orders": fake_resource})
    _capture_source(monkeypatch, fake_src)

    captured_incr_kwargs: dict = {}
    real_incremental_module = __import__("dlt.sources", fromlist=["incremental"])

    def _fake_inc(col, **kwargs):
        captured_incr_kwargs["col"] = col
        captured_incr_kwargs.update(kwargs)
        return object()

    monkeypatch.setattr(real_incremental_module, "incremental", _fake_inc)

    sql_dlt_source(
        "mysql+pymysql", _conn(),
        {"tables": ["orders"], "incremental_key": "created_at"},
    )

    fake_resource.apply_hints.assert_called_once()
    assert captured_incr_kwargs["col"] == "created_at"
    end_value = captured_incr_kwargs["end_value"]
    assert isinstance(end_value, datetime)
    assert end_value.hour == 0 and end_value.minute == 0 and end_value.second == 0
    assert end_value.tzinfo is not None
    assert end_value.tzinfo.utcoffset(end_value) == timezone.utc.utcoffset(end_value)
    # No initial_value supplied → 1900-01-01 UTC sentinel (dlt requires
    # initial_value whenever end_value is set; sentinel ≪ any real cursor).
    initial_value = captured_incr_kwargs["initial_value"]
    assert initial_value == datetime(1900, 1, 1, tzinfo=timezone.utc)


def test_sql_dlt_source_passes_initial_value_when_backfill(monkeypatch):
    """When `initial_value` is set (backfill / Load history), both bounds
    are applied: `[initial_value, end_value)`."""
    from datetime import datetime, timezone

    fake_resource = MagicMock()
    fake_src = SimpleNamespace(resources={"orders": fake_resource})
    _capture_source(monkeypatch, fake_src)

    captured_incr_kwargs: dict = {}
    real_incremental_module = __import__("dlt.sources", fromlist=["incremental"])
    monkeypatch.setattr(
        real_incremental_module, "incremental",
        lambda col, **kw: captured_incr_kwargs.update({"col": col, **kw}) or object(),
    )

    sql_dlt_source(
        "mysql+pymysql", _conn(),
        {"tables": ["orders"], "incremental_key": "created_at",
         "initial_value": "2025-01-01T00:00:00+00:00"},
    )

    assert captured_incr_kwargs["initial_value"] == datetime(
        2025, 1, 1, tzinfo=timezone.utc,
    )
    assert "end_value" in captured_incr_kwargs


def test_sql_dlt_source_skips_unknown_table(monkeypatch):
    """Resource missing for the configured table → no apply_hints, no crash."""
    fake_src = SimpleNamespace(resources={})
    _capture_source(monkeypatch, fake_src)
    # Should not raise even though "orders" has no resource on the fake source.
    sql_dlt_source(
        "mysql+pymysql", _conn(),
        {"tables": ["orders"], "incremental_key": "created_at"},
    )


# ── _detect_snapshot_date_column ─────────────────────────────────────────────

def test_detect_prefers_conventional_name():
    cols = [
        {"name": "ship_ts", "type": "timestamp"},
        {"name": "created_at", "type": "datetime"},
        {"name": "id", "type": "int"},
    ]
    assert tm._detect_snapshot_date_column(cols) == "created_at"


def test_detect_falls_back_to_first_date_typed():
    cols = [{"name": "id", "type": "int"}, {"name": "ship_ts", "type": "timestamp"}]
    assert tm._detect_snapshot_date_column(cols) == "ship_ts"


def test_detect_none_when_no_date_column():
    cols = [{"name": "id", "type": "int"}, {"name": "label", "type": "varchar"}]
    assert tm._detect_snapshot_date_column(cols) is None


# ── _apply_mysql_t1_schedule ─────────────────────────────────────────────────

def _pipe(tables, mode_initial="full"):
    return SimpleNamespace(
        id="p1", extraction_config={"tables": tables}, mode=mode_initial,
        cron=None, next_run_at=None, timezone="UTC", incremental_key=None,
    )


def _fake_connector(columns):
    return SimpleNamespace(
        get_table_schema=lambda table, schema=None: SimpleNamespace(columns=columns),
        close=lambda: None,
    )


def test_apply_incremental_seeds_initial_value_with_default_lookback(monkeypatch):
    """Default `first_ingest_lookback_days=1` → first-run lower bound = T-1
    (yesterday 00:00 UTC). dlt persists the cursor after run 1, so this is
    only consulted once."""
    from datetime import datetime, timezone
    from backend.config import settings

    monkeypatch.setattr(settings, "first_ingest_lookback_days", 1, raising=False)

    cols = [{"name": "created_at", "type": "datetime"}, {"name": "id", "type": "int"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: _fake_connector(cols),
    )
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=23), MagicMock())

    assert p.mode == "incremental"
    assert p.incremental_key == "created_at"
    assert p.cron == "0 2 * * *"
    assert p.next_run_at is not None
    assert p.extraction_config["tables"] == ["orders"]
    assert p.extraction_config["incremental_key"] == "created_at"
    iv = p.extraction_config["initial_value"]
    parsed = datetime.fromisoformat(iv)
    assert parsed.tzinfo is not None and parsed.tzinfo.utcoffset(parsed) == timezone.utc.utcoffset(parsed)
    assert parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0


def test_apply_incremental_no_initial_value_when_lookback_zero(monkeypatch):
    """`first_ingest_lookback_days=0` → no lower bound; first run pulls all
    history up to T-1 (bounded only by `end_value` at run time)."""
    from backend.config import settings
    monkeypatch.setattr(settings, "first_ingest_lookback_days", 0, raising=False)

    cols = [{"name": "created_at", "type": "datetime"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: _fake_connector(cols),
    )
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=23), MagicMock())

    assert p.mode == "incremental"
    assert p.incremental_key == "created_at"
    assert "initial_value" not in p.extraction_config


def test_apply_incremental_custom_lookback_n_days(monkeypatch):
    """`first_ingest_lookback_days=7` → first-run lower bound = today − 7 days
    00:00 UTC."""
    from datetime import datetime, timedelta, timezone
    from backend.config import settings
    monkeypatch.setattr(settings, "first_ingest_lookback_days", 7, raising=False)

    cols = [{"name": "created_at", "type": "datetime"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: _fake_connector(cols),
    )
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=23), MagicMock())

    expected = (datetime.now(timezone.utc) - timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    parsed = datetime.fromisoformat(p.extraction_config["initial_value"])
    # Allow 1 minute slack for test-clock crossing midnight.
    assert abs((parsed - expected).total_seconds()) < 60


def test_apply_full_snapshot_when_no_date_col(monkeypatch):
    cols = [{"name": "id", "type": "int"}, {"name": "label", "type": "varchar"}]
    monkeypatch.setattr(
        "backend.connectors.factory.get_connector_for_connection",
        lambda conn, db=None: _fake_connector(cols),
    )
    p = _pipe(["lookup"], mode_initial="incremental")  # start as incremental to verify override
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="mysql", id=1), MagicMock())

    assert p.mode == "full"
    assert p.cron == "0 2 * * *"
    assert "incremental_key" not in p.extraction_config
    assert "initial_value" not in p.extraction_config


def test_apply_noop_for_non_mysql(monkeypatch):
    called = {"opened": False}

    def _boom(conn, db=None):
        called["opened"] = True
        return _fake_connector([])

    monkeypatch.setattr("backend.connectors.factory.get_connector_for_connection", _boom)
    p = _pipe(["orders"])
    tm._apply_mysql_t1_schedule([p], SimpleNamespace(db_type="postgres", id=1), MagicMock())
    assert p.cron is None
    assert p.mode == "full"  # unchanged from initial
    assert called["opened"] is False  # never even opened a connector
