"""Tests for the Phase 3 stored-SQL dialect transpile (widgets BQ → DuckDB)."""
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
