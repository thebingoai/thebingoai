"""Tests for lean-param -> full widget JSON hydration (widget_specs/widgets.py).

Covers each BaseWidget subclass's build()/config/mapping, the BaseWidget
envelope, the _pick helper, build_widgets, and an end-to-end regression
(build -> verify -> layout) that guards the agent-omits-position contract.
"""

from backend.agents.dashboard_agent.widget_specs.widgets import (
    _pick,
    build_widgets,
    WIDGET_REGISTRY,
    BaseWidget,
    KpiWidget,
    ChartWidget,
    TableWidget,
    PivotTableWidget,
    FilterWidget,
    TextWidget,
    SectionWidget,
)


# --------------------------------------------------------------------------- #
# _pick helper
# --------------------------------------------------------------------------- #

def test_pick_drops_absent_and_none():
    params = {"a": 1, "b": None, "c": "x"}
    assert _pick(params, ("a", "b", "c", "d")) == {"a": 1, "c": "x"}


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

def test_registry_keys_match_types():
    assert set(WIDGET_REGISTRY) == {"kpi", "chart", "table", "pivot_table", "filter", "text", "section"}
    for wtype, builder in WIDGET_REGISTRY.items():
        assert builder.type == wtype
        assert isinstance(builder, BaseWidget)
        assert builder.params_doc  # spec source must be non-empty


# --------------------------------------------------------------------------- #
# KpiWidget
# --------------------------------------------------------------------------- #

def test_kpi_minimal_build():
    w = KpiWidget().build(
        {"label": "Rev", "valueColumn": "revenue", "connectionId": 1, "sql": "SELECT 1 AS revenue"},
        "kpi_1",
    )
    assert w["id"] == "kpi_1"
    assert w["widget"] == {"type": "kpi", "config": {"label": "Rev"}}
    assert w["dataSource"]["mapping"] == {"type": "kpi", "valueColumn": "revenue"}
    assert set(w["position"]) >= {"x", "y", "w", "h"}
    assert "sources" not in w  # omitted when absent


def test_kpi_full_config_and_trend_mapping():
    w = KpiWidget().build(
        {
            "label": "Rev", "prefix": "$", "suffix": "K",
            "compactNumbers": True, "roundValue": True, "decimalPlaces": 1,
            "comparison": {"type": "value", "targetValue": 100},
            "progressVisual": "bar",
            "valueColumn": "revenue", "aggregation": "sum",
            "autoTrend": True, "periodLabel": "vs last month",
            "trendDateColumn": "d", "trendValueColumn": "tv",
            "sparklineXColumn": "sx", "sparklineYColumn": "sy",
            "sparklineSortColumn": "ss", "sparklineSortDirection": "asc",
            "connectionId": 1, "sql": "SELECT 1",
        },
        "kpi_2",
    )
    cfg = w["widget"]["config"]
    assert cfg == {
        "label": "Rev", "prefix": "$", "suffix": "K", "compactNumbers": True,
        "roundValue": True, "decimalPlaces": 1,
        "comparison": {"type": "value", "targetValue": 100}, "progressVisual": "bar",
    }
    m = w["dataSource"]["mapping"]
    assert m == {
        "type": "kpi", "valueColumn": "revenue", "aggregation": "sum",
        "autoTrend": True, "periodLabel": "vs last month",
        "trendDateColumn": "d", "trendValueColumn": "tv",
        "sparklineXColumn": "sx", "sparklineYColumn": "sy",
        "sparklineSortColumn": "ss", "sparklineSortDirection": "asc",
    }


# --------------------------------------------------------------------------- #
# ChartWidget
# --------------------------------------------------------------------------- #

def test_chart_config_type_options_animation():
    w = ChartWidget().build(
        {
            "chartType": "bar", "title": "T", "description": "D",
            "options": {"stacked": "standard", "showLegend": True},
            "animation": {"entrance": "fadeIn"},
            "labelColumn": "region",
            "datasetColumns": [{"column": "revenue", "label": "Revenue"}],
            "connectionId": 1, "sql": "SELECT region, revenue FROM t",
        },
        "chart_1",
    )
    assert w["widget"]["config"] == {
        "type": "bar", "title": "T", "description": "D",
        "options": {"stacked": "standard", "showLegend": True},
        "animation": {"entrance": "fadeIn"},
    }
    m = w["dataSource"]["mapping"]
    assert m == {
        "type": "chart", "chartType": "bar",
        "labelColumn": "region",
        "datasetColumns": [{"column": "revenue", "label": "Revenue"}],
    }


def test_chart_scatter_metric_columns_and_charttype():
    w = ChartWidget().build(
        {
            "chartType": "scatter",
            "xMetricColumn": "ts", "yMetricColumn": "bpm",
            "xAggregation": "avg", "yAggregation": "avg",
            "connectionId": 1, "sql": "SELECT ts, bpm FROM m",
        },
        "chart_s",
    )
    assert w["widget"]["config"]["type"] == "scatter"
    m = w["dataSource"]["mapping"]
    assert m["chartType"] == "scatter"  # scatter {x,y} depends on it
    assert m["xMetricColumn"] == "ts" and m["yMetricColumn"] == "bpm"
    assert m["xAggregation"] == "avg" and m["yAggregation"] == "avg"
    assert "labelColumn" not in m


# --------------------------------------------------------------------------- #
# TableWidget
# --------------------------------------------------------------------------- #

def test_table_columns_once_feed_config_and_mapping():
    w = TableWidget().build(
        {
            "title": "Top", "pagination": True, "rowsPerPage": 25,
            "showSummaryRow": True, "defaultSortKey": "price", "defaultSortDir": "desc",
            "columns": [
                {"column": "address", "label": "Address"},
                {"column": "price", "label": "Price", "sortable": True, "filterable": True,
                 "format": "currency", "role": "metric", "displayType": "bar",
                 "showBarValue": True, "compactNumbers": True, "aggregation": "sum",
                 "comparisonCalc": "percentOfTotal", "runningCalc": "runningSum"},
            ],
            "connectionId": 1, "sql": "SELECT address, price FROM listings",
        },
        "table_1",
    )
    cfg = w["widget"]["config"]
    # config.columns uses `key`, only the display-light fields
    assert cfg["columns"] == [
        {"key": "address", "label": "Address"},
        {"key": "price", "label": "Price", "sortable": True, "filterable": True, "format": "currency"},
    ]
    assert cfg["title"] == "Top" and cfg["pagination"] is True and cfg["rowsPerPage"] == 25
    assert cfg["showSummaryRow"] is True and cfg["defaultSortKey"] == "price" and cfg["defaultSortDir"] == "desc"
    # mapping.columnConfig uses `column` + ALL extended display fields
    cc = w["dataSource"]["mapping"]["columnConfig"]
    assert cc[0] == {"column": "address", "label": "Address"}
    assert cc[1] == {
        "column": "price", "label": "Price", "sortable": True, "filterable": True,
        "format": "currency", "role": "metric", "displayType": "bar",
        "showBarValue": True, "compactNumbers": True, "aggregation": "sum",
        "comparisonCalc": "percentOfTotal", "runningCalc": "runningSum",
    }


# --------------------------------------------------------------------------- #
# PivotTableWidget
# --------------------------------------------------------------------------- #

def test_pivot_config_and_deduped_columnconfig():
    w = PivotTableWidget().build(
        {
            "title": "P",
            "rowDimensions": [{"column": "region", "label": "Region"}],
            "columnDimensions": [{"column": "quarter"}],
            "values": [
                {"column": "revenue", "label": "Revenue", "aggregation": "sum"},
                {"column": "region", "label": "dup"},  # duplicate column
            ],
            "expandCollapse": True, "defaultExpandLevel": 1,
            "showRowTotals": False, "showColumnTotals": True,
            "rowLimit": 50, "columnLimit": 10, "sortBy": "revenue", "sortDir": "desc",
            "connectionId": 1, "sql": "SELECT region, quarter, revenue FROM s",
        },
        "pivot_1",
    )
    cfg = w["widget"]["config"]
    assert cfg["values"][0]["aggregation"] == "sum"  # aggregation kept in config
    assert cfg["expandCollapse"] is True and cfg["sortDir"] == "desc"
    cc = w["dataSource"]["mapping"]["columnConfig"]
    assert [c["column"] for c in cc] == ["region", "quarter", "revenue"]  # union, first-wins
    # columnConfig carries only column + label (no aggregation)
    assert all(set(c) <= {"column", "label"} for c in cc)
    assert w["dataSource"]["mapping"]["type"] == "pivot_table"


# --------------------------------------------------------------------------- #
# Filter / Text (no dataSource)
# --------------------------------------------------------------------------- #

def test_filter_no_datasource_multiple_controls():
    w = FilterWidget().build(
        {"controls": [
            {"type": "dropdown", "label": "Region", "key": "r", "column": "region"},
            {"type": "date_range", "label": "Date", "key": "d", "column": "order_date",
             "dateRangeDefault": "full"},
        ]},
        "filter_1",
    )
    assert "dataSource" not in w
    assert len(w["widget"]["config"]["controls"]) == 2
    assert w["widget"]["config"]["controls"][1]["dateRangeDefault"] == "full"


def test_text_alignment_optional():
    full = TextWidget().build({"content": "## Detail", "alignment": "center"}, "t_1")
    bare = TextWidget().build({"content": "## Detail"}, "t_2")
    assert "dataSource" not in full
    # Markdown-heading content is auto-flagged isSection so the frontend groups it.
    assert full["widget"]["config"] == {"content": "## Detail", "alignment": "center", "isSection": True}
    assert bare["widget"]["config"] == {"content": "## Detail", "isSection": True}


def test_text_isSection_heuristic_and_explicit():
    heading = TextWidget().build({"content": "## Trends"}, "t_h")
    plain = TextWidget().build({"content": "just a note"}, "t_p")
    explicit = TextWidget().build({"content": "## Trends", "isSection": False}, "t_e")
    assert heading["widget"]["config"]["isSection"] is True   # '#'-prefixed → section
    assert plain["widget"]["config"]["isSection"] is False    # narrative → not a section
    assert explicit["widget"]["config"]["isSection"] is False  # explicit flag wins


# --------------------------------------------------------------------------- #
# SectionWidget (no dataSource)
# --------------------------------------------------------------------------- #

def test_section_minimal_build():
    w = SectionWidget().build({"title": "Trends & Breakdown"}, "section_1")
    assert w["id"] == "section_1"
    assert w["widget"] == {"type": "section", "config": {"title": "Trends & Breakdown"}}
    assert "dataSource" not in w          # has_data_source = False
    assert "sources" not in w
    # Default section layout: full-width, single-row band.
    assert w["position"]["w"] == 12 and w["position"]["h"] == 1


def test_section_color_clamp():
    ok = SectionWidget().build({"title": "T", "sectionColor": "violet"}, "s_ok")
    bad = SectionWidget().build({"title": "T", "sectionColor": "chartreuse"}, "s_bad")
    assert ok["widget"]["config"]["sectionColor"] == "violet"   # known token kept
    assert "sectionColor" not in bad["widget"]["config"]        # unknown token dropped


# --------------------------------------------------------------------------- #
# BaseWidget envelope
# --------------------------------------------------------------------------- #

def test_sources_included_when_present():
    w = KpiWidget().build(
        {"label": "X", "valueColumn": "v", "connectionId": 1, "sql": "SELECT 1", "sources": ["orders"]},
        "k",
    )
    assert w["sources"] == ["orders"]


def test_width_hint_seeds_position_w():
    w = ChartWidget().build(
        {"chartType": "line", "labelColumn": "d", "datasetColumns": [],
         "connectionId": 1, "sql": "SELECT 1", "width": 8},
        "chart_w",
    )
    assert w["position"]["w"] == 8


def test_default_position_per_type():
    assert KpiWidget().build({"label": "x", "valueColumn": "v", "connectionId": 1, "sql": "s"}, "i")["position"]["w"] == 3
    assert TableWidget().build({"columns": [], "connectionId": 1, "sql": "s"}, "i")["position"]["w"] == 12
    assert FilterWidget().build({"controls": []}, "i")["position"]["h"] == 2


# --------------------------------------------------------------------------- #
# build_widgets
# --------------------------------------------------------------------------- #

def test_build_widgets_id_autogen_and_passthrough():
    full_widget = {"id": "keep", "position": {"x": 0, "y": 0, "w": 6, "h": 5},
                   "widget": {"type": "chart", "config": {"type": "bar"}}}
    out = build_widgets([
        {"type": "text", "content": "## A"},   # hydrated, auto id text_0
        full_widget,                            # passthrough (has "widget")
        {"type": "bogus", "foo": 1},            # passthrough (unknown type)
        "not-a-dict",                           # passthrough (non-dict)
    ])
    assert out[0]["id"] == "text_0" and out[0]["widget"]["type"] == "text"
    assert out[1] is full_widget
    assert out[2] == {"type": "bogus", "foo": 1}
    assert out[3] == "not-a-dict"


def test_build_widgets_preserves_explicit_id():
    out = build_widgets([{"type": "kpi", "id": "my_kpi", "label": "X",
                          "valueColumn": "v", "connectionId": 1, "sql": "SELECT 1 AS v"}])
    assert out[0]["id"] == "my_kpi"


def test_build_widgets_non_list_and_empty():
    assert build_widgets("nope") == "nope"
    assert build_widgets([]) == []


# --------------------------------------------------------------------------- #
# Integration: build -> verify -> layout (agent omits position)
# --------------------------------------------------------------------------- #

def test_lean_dashboard_verifies_and_lays_out():
    from backend.agents.dashboard_tools import _verify_widgets
    from backend.agents.dashboard_layout import normalize_dashboard_layout

    lean = [{"type": "filter", "controls": [{"type": "dropdown", "label": "R", "key": "r", "column": "r"}]}]
    for i in range(4):
        # aggregation is explicit: the kpi_not_aggregated gate requires either
        # aggregating SQL or an explicit aggregation on every KPI.
        lean.append({"type": "kpi", "label": f"M{i}", "valueColumn": "v", "aggregation": "sum",
                     "connectionId": 1, "sql": "SELECT 1 AS v"})
    lean += [
        {"type": "chart", "chartType": "bar", "labelColumn": "r",
         "datasetColumns": [{"column": "v", "label": "V", "aggregation": "sum"}],
         "connectionId": 1, "sql": "SELECT r,v FROM t"},
        {"type": "chart", "chartType": "line", "labelColumn": "d",
         "datasetColumns": [{"column": "v", "label": "V", "aggregation": "sum"}],
         "connectionId": 1, "sql": "SELECT d,v FROM t"},
        {"type": "text", "content": "## Detail"},
        {"type": "table", "columns": [{"column": "a", "label": "A"}], "connectionId": 1, "sql": "SELECT a FROM t"},
    ]
    full = build_widgets(lean)

    # Hydrated widgets pass the pre-persistence gate (build() seeds full shape).
    assert _verify_widgets(full, None) == []

    # Layout reflows from emission order alone — no agent-supplied position.
    normalize_dashboard_layout(full)
    rows: dict[int, list] = {}
    for w in full:
        rows.setdefault(w["position"]["y"], []).append((w["widget"]["type"], w["position"]["w"]))
    ys = sorted(rows)
    assert rows[ys[0]] == [("filter", 12)]
    assert rows[ys[1]] == [("kpi", 3), ("kpi", 3), ("kpi", 3), ("kpi", 3)]
    assert sorted(t for t, _ in rows[ys[2]]) == ["chart", "chart"]
    assert all(w == 6 for _, w in rows[ys[2]])
    assert ("text", 12) in rows[ys[3]]
    assert ("table", 12) in rows[ys[4]]


# --------------------------------------------------------------------------- #
# Aggregation guard (_verify_widgets -> chart_not_aggregated)
# --------------------------------------------------------------------------- #

def _chart_widget(chart_type, sql, dataset_columns=None, title="T"):
    """Build a category-chart widget in the SHAPE the agent would emit (after
    build_widgets hydration) so _verify_widgets accepts the envelope."""
    return {
        "id": "w_test",
        "position": {"x": 0, "y": 0, "w": 6, "h": 5},
        "widget": {"type": "chart", "config": {"type": chart_type, "title": title}},
        "dataSource": {
            "connectionId": 1,
            "sql": sql,
            "mapping": {
                "type": "chart", "chartType": chart_type,
                "labelColumn": "lbl", "datasetColumns": dataset_columns or [],
            },
        },
    }


def test_aggregation_guard_rejects_raw_row_pie():
    """Reproduces the real regression: 'Attrition by Role' emitted
    `SELECT role, left AS attritions FROM t WHERE left=1` — no GROUP BY, no
    aggregate fn, no `aggregation` on datasetColumns."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _chart_widget(
        "pie",
        "SELECT role, `left` AS attritions FROM `csv_24` c WHERE c.`left` = 1",
        [{"column": "attritions", "label": "Attritions"}],
    )
    v = _verify_widgets([w], None)
    assert any(x.get("code") == "chart_not_aggregated" for x in v), v


def test_aggregation_guard_passes_aggregated_sql():
    from backend.agents.dashboard_tools import _verify_widgets
    w = _chart_widget(
        "bar",
        "SELECT o.region, SUM(o.amount) AS revenue FROM orders o GROUP BY o.region",
        [{"column": "revenue", "label": "Revenue"}],
    )
    assert not any(x.get("code") == "chart_not_aggregated" for x in _verify_widgets([w], None))


def test_aggregation_guard_passes_explicit_aggregation_on_datasetcolumns():
    """Escape hatch: pre-aggregated source table — agent declares aggregation
    on datasetColumns and the transform groups-by labelColumn itself."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _chart_widget(
        "bar",
        "SELECT region, daily_revenue FROM daily_sales",   # raw rows, no GROUP BY
        [{"column": "daily_revenue", "label": "Revenue", "aggregation": "sum"}],
    )
    assert not any(x.get("code") == "chart_not_aggregated" for x in _verify_widgets([w], None))


def test_aggregation_guard_exempts_scatter():
    """Scatter takes raw X/Y metric pairs — must never be forced through the
    aggregation check."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _chart_widget(
        "scatter",
        "SELECT ts, bpm FROM heart_rate",   # raw rows
        [{"column": "ts", "label": "TS"}, {"column": "bpm", "label": "BPM"}],
    )
    v = _verify_widgets([w], None)
    assert not any(x.get("code") == "chart_not_aggregated" for x in v)


def test_aggregation_guard_fires_for_each_category_type():
    from backend.agents.dashboard_tools import _verify_widgets
    for ct in ("bar", "pie", "line", "area", "doughnut"):
        w = _chart_widget(ct, "SELECT region, sales FROM t", [{"column": "sales", "label": "S"}])
        v = _verify_widgets([w], None)
        assert any(x.get("code") == "chart_not_aggregated" for x in v), (ct, v)


# --------------------------------------------------------------------------- #
# Aggregation guard (_verify_widgets -> kpi_not_aggregated)
# --------------------------------------------------------------------------- #

def _kpi_widget(sql, aggregation=None, label="Total Revenue"):
    """Build a KPI widget in the SHAPE the agent emits after build_widgets
    hydration. `aggregation=None` reproduces the omission `_pick` allows."""
    mapping = {"type": "kpi", "valueColumn": "total_revenue_usd"}
    if aggregation is not None:
        mapping["aggregation"] = aggregation
    return {
        "id": "kpi_1",
        "position": {"x": 0, "y": 0, "w": 3, "h": 2},
        "widget": {"type": "kpi", "config": {"label": label}},
        "dataSource": {"connectionId": 1, "sql": sql, "mapping": mapping},
    }


def test_kpi_guard_rejects_raw_rows_without_aggregation():
    """Reproduces the reported bug: a 15k-row raw SELECT with no
    mapping.aggregation renders row 0 as the headline."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _kpi_widget(
        "SELECT c.sale_date, c.revenue_usd AS total_revenue_usd FROM csv_162 c ORDER BY c.sale_date"
    )
    v = _verify_widgets([w], None)
    assert any(x.get("code") == "kpi_not_aggregated" for x in v), v


def test_kpi_guard_passes_with_explicit_aggregation():
    """Escape hatch: raw rows are fine when the transform is told how to
    collapse them."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _kpi_widget(
        "SELECT c.sale_date, c.revenue_usd AS total_revenue_usd FROM csv_162 c",
        aggregation="sum",
    )
    assert not any(x.get("code") == "kpi_not_aggregated" for x in _verify_widgets([w], None))


def test_kpi_guard_passes_aggregated_sql():
    """SQL that already collapses to one row needs no mapping.aggregation."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _kpi_widget("SELECT SUM(c.revenue_usd) AS total_revenue_usd FROM csv_162 c")
    assert not any(x.get("code") == "kpi_not_aggregated" for x in _verify_widgets([w], None))


def test_kpi_guard_survives_a_label_less_widget():
    """A KPI whose config has neither label nor title must yield a violation,
    not an IndexError from cfg_title_for's empty-content fallback."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _kpi_widget("SELECT d, v AS total_revenue_usd FROM t")
    w["widget"]["config"] = {}
    v = _verify_widgets([w], None)
    assert any(x.get("code") == "kpi_not_aggregated" for x in v), v


def test_chart_guard_survives_a_title_less_widget():
    """Same latent crash on the pre-existing chart rule: a bar chart with only
    a `type` in its config used to raise instead of reporting."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _chart_widget("bar", "SELECT region, sales FROM t", [{"column": "sales", "label": "S"}])
    w["widget"]["config"] = {"type": "bar"}
    v = _verify_widgets([w], None)
    assert any(x.get("code") == "chart_not_aggregated" for x in v), v


def test_kpi_guard_ignores_non_kpi_widgets():
    """The rule keys off widget.type — a chart must not collect it."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _chart_widget("bar", "SELECT region, sales FROM t", [{"column": "sales", "label": "S"}])
    assert not any(x.get("code") == "kpi_not_aggregated" for x in _verify_widgets([w], None))


def test_kpi_guard_rejects_an_unknown_aggregation():
    """Any truthy aggregation used to pass the guard, but the transform treats
    a method it doesn't know as absent — the stated intent is lost silently."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _kpi_widget("SELECT d, v AS total_revenue_usd FROM t", aggregation="average")
    codes = [x.get("code") for x in _verify_widgets([w], None)]
    assert "kpi_invalid_aggregation" in codes, codes
    assert "kpi_not_aggregated" not in codes, codes


def test_guards_skip_a_malformed_data_source():
    """A non-dict dataSource is reported once as invalid_dataSource; the
    aggregation guards must not then call .get() on it and crash."""
    from backend.agents.dashboard_tools import _verify_widgets
    w = _kpi_widget("SELECT 1 AS total_revenue_usd")
    w["dataSource"] = "SELECT 1 AS total_revenue_usd"
    codes = [x.get("code") for x in _verify_widgets([w], None)]
    assert codes == ["invalid_dataSource"], codes


# --------------------------------------------------------------------------- #
# Dialect hints for db_type='dataset' (CSV/Excel via bingo-csv-connector)
# --------------------------------------------------------------------------- #

def test_dialect_hints_dataset_dev_returns_duckdb():
    """Dev (DISABLE_LOCAL_DATA_PLANE=false): dataset connections emit DuckDB hints
    so the agent doesn't write BigQuery-only SQL (`SAFE_CAST`, backticks)."""
    from backend.agents.profile_defaults import (
        DUCKDB_DIALECT_HINTS, BIGQUERY_DIALECT_HINTS, _dialect_hints_for_target,
    )
    from backend.config import settings as _settings
    saved = getattr(_settings, "disable_local_data_plane", None)
    try:
        _settings.disable_local_data_plane = False
        out = _dialect_hints_for_target(org_id=None, target_db_type="dataset")
        assert out == DUCKDB_DIALECT_HINTS
        assert out != BIGQUERY_DIALECT_HINTS
    finally:
        _settings.disable_local_data_plane = saved


def test_dialect_hints_dataset_lockdown_returns_bigquery():
    """Lockdown (DISABLE_LOCAL_DATA_PLANE=true): dataset writes to BQ → BigQuery hints."""
    from backend.agents.profile_defaults import (
        DUCKDB_DIALECT_HINTS, BIGQUERY_DIALECT_HINTS, _dialect_hints_for_target,
    )
    from backend.config import settings as _settings
    saved = getattr(_settings, "disable_local_data_plane", None)
    try:
        _settings.disable_local_data_plane = True
        out = _dialect_hints_for_target(org_id=None, target_db_type="dataset")
        assert out == BIGQUERY_DIALECT_HINTS
        assert out != DUCKDB_DIALECT_HINTS
    finally:
        _settings.disable_local_data_plane = saved


def test_kpi_guard_rejects_a_window_aggregate():
    """`SUM(x) OVER ()` matches the aggregate regex but is a window function: it
    returns one row per input row, each holding the same total. Passing the guard
    lets the KPI omit mapping.aggregation, and the multi-row default then sums
    those identical rows — the headline is the total times the row count."""
    from backend.agents.dashboard_tools import _verify_widgets

    w = _kpi_widget("SELECT SUM(c.revenue_usd) OVER () AS total_revenue_usd FROM csv_162 c")
    codes = [x.get("code") for x in _verify_widgets([w], None)]
    assert "kpi_not_aggregated" in codes, codes


def test_kpi_guard_still_accepts_real_aggregation():
    from backend.agents.dashboard_tools import _is_aggregated_sql

    assert _is_aggregated_sql("SELECT SUM(revenue_usd) AS t FROM csv_162")
    assert _is_aggregated_sql("SELECT d, COUNT(*) AS n FROM csv_162 GROUP BY d")
    # Window function alone is not aggregation.
    assert not _is_aggregated_sql("SELECT SUM(v) OVER () AS t FROM csv_162")
    assert not _is_aggregated_sql("SELECT d, v FROM csv_162")
    # SQL the parser rejects falls back to the textual check rather than
    # reporting "not aggregated" for something that plainly is.
    assert _is_aggregated_sql("SELECT COUNT(* FROM broken")
