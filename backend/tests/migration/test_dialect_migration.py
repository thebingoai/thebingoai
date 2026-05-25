"""Tests for the Phase 3 stored-SQL dialect transpile (widgets BQ → DuckDB)
and the per-dashboard cutover orchestration (journal + rollback)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import backend.migration.dialect_migration as dm
from backend.migration.dialect_migration import transpile_dashboard_widgets


def _widget(wid, sql, mapping=None):
    ds = {"sql": sql, "connectionId": 1}
    if mapping is not None:
        ds["mapping"] = mapping
    return {"id": wid, "dataSource": ds, "widget": {"config": {"type": "table"}}}


def test_transpiles_bq_widgets_and_preserves_mapping():
    widgets = [
        _widget("w1", "SELECT DATE_TRUNC(`d`, DAY) AS d FROM `csv_1`", mapping={"type": "table"}),
    ]
    res = transpile_dashboard_widgets(widgets)

    assert res.ok is True
    assert res.changed is True
    assert len(res.rewrites) == 1
    new_sql = widgets[0]["dataSource"]["sql"]
    assert "`" not in new_sql                       # backticks gone
    assert widgets[0]["dataSource"]["mapping"] == {"type": "table"}  # mapping preserved
    assert widgets[0]["dataSource"]["connectionId"] == 1


def test_unparseable_widget_is_flagged_not_rewritten():
    original = "SELECT ST_GEOGPOINT(lng, lat) FROM `t`"
    widgets = [_widget("w1", original)]
    res = transpile_dashboard_widgets(widgets)

    assert res.ok is False                          # halt this dashboard's cutover
    assert res.unparseable == ["w1"]
    assert widgets[0]["dataSource"]["sql"] == original  # left untouched


def test_dry_run_does_not_mutate():
    original = "SELECT `x` FROM `t`"
    widgets = [_widget("w1", original)]
    res = transpile_dashboard_widgets(widgets, dry_run=True)

    assert len(res.rewrites) == 1                   # rewrite computed
    assert res.changed is False
    assert widgets[0]["dataSource"]["sql"] == original  # not mutated


def test_mixed_dashboard_partial_ok_is_not_ok():
    widgets = [
        _widget("w1", "SELECT `a` FROM `t`"),
        _widget("w2", "SELECT ST_GEOGPOINT(a, b) FROM `t`"),
    ]
    res = transpile_dashboard_widgets(widgets, dry_run=True)
    assert res.unparseable == ["w2"]
    assert res.ok is False
    assert [r.widget_id for r in res.rewrites] == ["w1"]


def test_widget_without_sql_skipped():
    widgets = [{"id": "w1", "widget": {"config": {}}}, {"id": "w2", "dataSource": {"mapping": {}}}]
    res = transpile_dashboard_widgets(widgets)
    assert res.rewrites == [] and res.unparseable == [] and res.changed is False


# --- Orchestration (journal + rollback) ------------------------------------

def test_is_duckdb_ready():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = object()
    assert dm.is_duckdb_ready(5, db) is True
    db.query.return_value.filter.return_value.first.return_value = None
    assert dm.is_duckdb_ready(5, db) is False
    assert dm.is_duckdb_ready(None, db) is False


def test_migrate_dashboard_migrated(monkeypatch):
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda did, db: False)
    db = MagicMock()
    dash = SimpleNamespace(id=5, widgets=[_widget("w1", "SELECT `x` FROM `t`")])
    out = dm.migrate_dashboard(dash, db=db)
    assert out.status == "migrated"
    assert "`" not in dash.widgets[0]["dataSource"]["sql"]
    db.commit.assert_called_once()


def test_migrate_dashboard_halts_on_unparseable(monkeypatch):
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda did, db: False)
    original = "SELECT ST_GEOGPOINT(a, b) FROM `t`"
    dash = SimpleNamespace(id=6, widgets=[_widget("w1", original)])
    out = dm.migrate_dashboard(dash, db=MagicMock())
    assert out.status == "halted"
    assert out.unparseable == ["w1"]
    assert dash.widgets[0]["dataSource"]["sql"] == original  # untouched


def test_migrate_dashboard_dry_run_no_mutation(monkeypatch):
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda did, db: False)
    original = "SELECT `x` FROM `t`"
    dash = SimpleNamespace(id=6, widgets=[_widget("w1", original)])
    out = dm.migrate_dashboard(dash, dry_run=True, db=MagicMock())
    assert out.status == "dry_run"
    assert dash.widgets[0]["dataSource"]["sql"] == original


def test_migrate_dashboard_skips_already_journaled(monkeypatch):
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda did, db: True)
    out = dm.migrate_dashboard(SimpleNamespace(id=7, widgets=[]), db=MagicMock())
    assert out.status == "skipped"


def test_mark_born_duckdb(monkeypatch):
    monkeypatch.setattr(dm, "is_duckdb_ready", lambda did, db: False)
    db = MagicMock()
    dm.mark_born_duckdb(9, db)
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_rollback_restores_original_sql():
    db = MagicMock()
    journal = SimpleNamespace(
        status="migrated",
        widget_rewrites=[{"widget_id": "w1", "old_sql": "SELECT `x` FROM `t`"}],
    )
    dash = SimpleNamespace(id=5, widgets=[_widget("w1", 'SELECT "x" FROM "t"')])
    db.query.return_value.filter.return_value.first.side_effect = [journal, dash]
    out = dm.rollback_dashboard(5, db=db)
    assert out == "rolled_back"
    assert dash.widgets[0]["dataSource"]["sql"] == "SELECT `x` FROM `t`"
    db.delete.assert_called_once_with(journal)


def test_rollback_noop_for_born_duckdb():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(status="born_duckdb")
    assert dm.rollback_dashboard(5, db=db) == "no_op"
