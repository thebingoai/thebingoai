"""Tests for the deterministic dashboard layout normalizer."""
import copy

from backend.agents.dashboard_layout import GRID_COLUMNS, normalize_dashboard_layout


def _w(wid, wtype, x, y, w, h, chart_type=None):
    config = {}
    if chart_type:
        config["type"] = chart_type
    return {
        "id": wid,
        "position": {"x": x, "y": y, "w": w, "h": h},
        "widget": {"type": wtype, "config": config},
    }


def _pos(widgets, wid):
    return next(w["position"] for w in widgets if w["id"] == wid)


def _well_formed():
    # Canonical section order: filter → KPI row → sections.
    return [
        _w("filter", "filter", 0, 0, 12, 2),
        _w("kpi1", "kpi", 0, 2, 3, 2),
        _w("kpi2", "kpi", 3, 2, 3, 2),
        _w("kpi3", "kpi", 6, 2, 3, 2),
        _w("kpi4", "kpi", 9, 2, 3, 2),
        _w("header1", "text", 0, 4, 12, 1),
        _w("chart1", "chart", 0, 5, 6, 5, "bar"),
        _w("chart2", "chart", 6, 5, 6, 5, "line"),
        _w("table", "table", 0, 10, 12, 5),
    ]


class TestIdempotency:
    def test_well_formed_layout_unchanged(self):
        widgets = _well_formed()
        before = copy.deepcopy([w["position"] for w in widgets])
        normalize_dashboard_layout(widgets)
        assert [w["position"] for w in widgets] == before

    def test_double_normalize_is_stable(self):
        widgets = [
            _w("a", "chart", 0, 0, 5, 5, "bar"),
            _w("b", "chart", 5, 0, 5, 5, "line"),
            _w("c", "chart", 0, 8, 8, 5, "area"),
        ]
        normalize_dashboard_layout(widgets)
        once = copy.deepcopy([w["position"] for w in widgets])
        normalize_dashboard_layout(widgets)
        assert [w["position"] for w in widgets] == once

    def test_empty_list(self):
        assert normalize_dashboard_layout([]) == []


class TestRowWidthNormalization:
    def test_two_charts_w5_become_6_6(self):
        widgets = [
            _w("a", "chart", 0, 0, 5, 5, "bar"),
            _w("b", "chart", 5, 0, 5, 5, "line"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a") == {"x": 0, "y": 0, "w": 6, "h": 5}
        assert _pos(widgets, "b") == {"x": 6, "y": 0, "w": 6, "h": 5}

    def test_three_charts_w3_become_4_4_4(self):
        widgets = [
            _w("a", "chart", 0, 0, 3, 5, "bar"),
            _w("b", "chart", 3, 0, 3, 5, "line"),
            _w("c", "chart", 6, 0, 3, 5, "area"),
        ]
        normalize_dashboard_layout(widgets)
        assert [_pos(widgets, i)["w"] for i in "abc"] == [4, 4, 4]
        assert [_pos(widgets, i)["x"] for i in "abc"] == [0, 4, 8]

    def test_chart_and_pivot_4_6_become_4_8(self):
        widgets = [
            _w("a", "chart", 0, 0, 4, 5, "bar"),
            _w("b", "pivot_table", 4, 0, 6, 5),
        ]
        normalize_dashboard_layout(widgets)
        total = _pos(widgets, "a")["w"] + _pos(widgets, "b")["w"]
        assert total == GRID_COLUMNS
        # Deficit split proportionally — larger widget gets more.
        assert _pos(widgets, "b")["w"] > _pos(widgets, "a")["w"]
        assert _pos(widgets, "a")["x"] == 0
        assert _pos(widgets, "b")["x"] == _pos(widgets, "a")["w"]

    def test_lone_chart_widens_to_12(self):
        widgets = [_w("a", "chart", 0, 0, 8, 5, "line")]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a") == {"x": 0, "y": 0, "w": 12, "h": 5}

    def test_lone_text_header_widens_to_12(self):
        widgets = [_w("h", "text", 0, 0, 4, 1)]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "h")["w"] == 12

    def test_lone_pie_widens_to_full_width(self):
        # Per-type pie cap is waived when the widget is alone in its row.
        widgets = [_w("p", "chart", 0, 0, 4, 5, "pie")]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "p")["w"] == 12
        assert _pos(widgets, "p")["x"] == 0

    def test_pie_plus_bar_pie_capped_bar_takes_rest(self):
        widgets = [
            _w("p", "chart", 0, 0, 4, 5, "doughnut"),
            _w("b", "chart", 4, 0, 4, 5, "bar"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "p")["w"] <= 6
        assert _pos(widgets, "p")["w"] + _pos(widgets, "b")["w"] == GRID_COLUMNS

    def test_lone_kpi_capped_at_6(self):
        widgets = [_w("k", "kpi", 0, 0, 3, 2)]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "k")["w"] == 6

    def test_three_kpis_w3_become_4_4_4(self):
        widgets = [
            _w("k1", "kpi", 0, 0, 3, 2),
            _w("k2", "kpi", 3, 0, 3, 2),
            _w("k3", "kpi", 6, 0, 3, 2),
        ]
        normalize_dashboard_layout(widgets)
        assert [_pos(widgets, f"k{i}")["w"] for i in (1, 2, 3)] == [4, 4, 4]

    def test_five_kpis_one_row_full_width(self):
        widgets = [_w(f"k{i}", "kpi", 0, 0, 3, 2) for i in range(1, 6)]
        normalize_dashboard_layout(widgets)
        ws = [_pos(widgets, f"k{i}")["w"] for i in range(1, 6)]
        assert ws == [3, 3, 2, 2, 2]  # divmod(12, 5) → fills the row exactly
        assert sum(ws) == 12
        assert all(_pos(widgets, f"k{i}")["y"] == 0 for i in range(1, 6))

    def _kpi_rows(self, n):
        widgets = [_w(f"k{i}", "kpi", 0, 0, 3, 2) for i in range(1, n + 1)]
        normalize_dashboard_layout(widgets)
        rows: dict[int, list[int]] = {}
        for i in range(1, n + 1):
            p = _pos(widgets, f"k{i}")
            rows.setdefault(p["y"], []).append(p["w"])
        return [rows[y] for y in sorted(rows)]

    def test_six_kpis_split_3_3(self):
        # Not 5 + 1: the lone sixth card would sit capped at w=6 beside half a row of nothing.
        rows = self._kpi_rows(6)
        assert [len(r) for r in rows] == [3, 3]
        assert all(sum(r) == 12 for r in rows)

    def test_seven_kpis_split_4_3(self):
        rows = self._kpi_rows(7)
        assert [len(r) for r in rows] == [4, 3]
        assert all(sum(r) == 12 for r in rows)

    def test_eleven_kpis_split_4_4_3(self):
        rows = self._kpi_rows(11)
        assert [len(r) for r in rows] == [4, 4, 3]
        assert all(sum(r) == 12 for r in rows)


class TestPairUp:
    def test_two_stacked_lone_charts_merge_side_by_side(self):
        widgets = [
            _w("a", "chart", 0, 0, 6, 5, "bar"),
            _w("b", "chart", 0, 5, 6, 5, "line"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a") == {"x": 0, "y": 0, "w": 6, "h": 5}
        assert _pos(widgets, "b") == {"x": 6, "y": 0, "w": 6, "h": 5}

    def test_three_stacked_lone_charts_pair_plus_full_width(self):
        widgets = [
            _w("a", "chart", 0, 0, 6, 5, "bar"),
            _w("b", "chart", 0, 5, 6, 5, "line"),
            _w("c", "chart", 0, 10, 6, 5, "area"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a")["y"] == _pos(widgets, "b")["y"] == 0
        assert _pos(widgets, "a")["w"] + _pos(widgets, "b")["w"] == 12
        # Odd one out: full width on the next row.
        assert _pos(widgets, "c") == {"x": 0, "y": 5, "w": 12, "h": 5}

    def test_chart_and_pivot_pair(self):
        widgets = [
            _w("c", "chart", 0, 0, 6, 5, "bar"),
            _w("p", "pivot_table", 0, 5, 8, 5),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "c")["y"] == _pos(widgets, "p")["y"] == 0
        assert _pos(widgets, "c")["w"] + _pos(widgets, "p")["w"] == 12

    def test_chart_and_table_not_paired(self):
        widgets = [
            _w("c", "chart", 0, 0, 6, 5, "bar"),
            _w("t", "table", 0, 5, 12, 5),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "c") == {"x": 0, "y": 0, "w": 12, "h": 5}
        assert _pos(widgets, "t") == {"x": 0, "y": 5, "w": 12, "h": 5}

    def test_different_heights_paired_with_uniform_height(self):
        # Reflow gives every row a uniform height (max of members), so two
        # stacked charts of different heights still pair cleanly.
        widgets = [
            _w("a", "chart", 0, 0, 6, 5, "bar"),
            _w("b", "chart", 0, 5, 6, 7, "line"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a")["y"] == _pos(widgets, "b")["y"] == 0
        assert _pos(widgets, "a")["h"] == _pos(widgets, "b")["h"] == 7
        assert _pos(widgets, "a")["w"] + _pos(widgets, "b")["w"] == 12

    def test_oversized_pair_squeezed_to_fit(self):
        # Two stacked charts wanting 8+8 shrink to 6+6 rather than stacking.
        widgets = [
            _w("a", "chart", 0, 0, 8, 5, "bar"),
            _w("b", "chart", 0, 5, 8, 5, "line"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a")["y"] == _pos(widgets, "b")["y"] == 0
        assert _pos(widgets, "a")["w"] + _pos(widgets, "b")["w"] == 12

    def test_full_width_chart_not_squeezed(self):
        # A w=12 chart (hero time-series) keeps its own row.
        widgets = [
            _w("a", "chart", 0, 0, 12, 6, "line"),
            _w("b", "chart", 0, 6, 6, 5, "bar"),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "a") == {"x": 0, "y": 0, "w": 12, "h": 6}
        assert _pos(widgets, "b") == {"x": 0, "y": 6, "w": 12, "h": 5}

    def test_paired_row_stable_on_second_run(self):
        widgets = [
            _w("a", "chart", 0, 0, 6, 5, "bar"),
            _w("b", "chart", 0, 5, 6, 5, "line"),
            _w("c", "chart", 0, 10, 6, 5, "area"),
        ]
        normalize_dashboard_layout(widgets)
        once = copy.deepcopy([w["position"] for w in widgets])
        normalize_dashboard_layout(widgets)
        assert [w["position"] for w in widgets] == once


class TestOverlapResolution:
    def test_two_full_width_same_y_stack(self):
        widgets = [
            _w("a", "table", 0, 0, 12, 5),
            _w("b", "table", 0, 0, 12, 5),
        ]
        normalize_dashboard_layout(widgets)
        ys = sorted(p["y"] for p in (_pos(widgets, "a"), _pos(widgets, "b")))
        assert ys == [0, 5]

    def test_partial_overlap_resolved(self):
        # Overlapping charts get pushed apart, then the pair-up pass merges
        # them into a clean side-by-side row.
        widgets = [
            _w("a", "chart", 0, 0, 8, 5, "bar"),
            _w("b", "chart", 4, 2, 8, 5, "line"),
        ]
        normalize_dashboard_layout(widgets)
        a, b = _pos(widgets, "a"), _pos(widgets, "b")
        no_y_overlap = a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"]
        no_x_overlap = a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
        assert no_y_overlap or no_x_overlap


class TestVerticalCompaction:
    def test_gap_between_sections_removed(self):
        widgets = [
            _w("k1", "kpi", 0, 0, 6, 2),
            _w("k2", "kpi", 6, 0, 6, 2),
            _w("t", "table", 0, 10, 12, 5),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "t")["y"] == 2

    def test_leading_gap_removed(self):
        widgets = [_w("t", "table", 0, 7, 12, 5)]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "t")["y"] == 0


class TestMixedHeightBand:
    def test_mosaic_reflowed_without_gaps(self):
        # Tall pivot beside two stacked charts — reflowed into uniform rows
        # with no horizontal gaps.
        widgets = [
            _w("c1", "chart", 0, 0, 8, 5, "bar"),
            _w("c2", "chart", 0, 5, 8, 5, "line"),
            _w("p", "pivot_table", 8, 0, 4, 10),
        ]
        normalize_dashboard_layout(widgets)
        rows = {}
        for w in widgets:
            rows.setdefault(w["position"]["y"], []).append(w["position"])
        for members in rows.values():
            assert sum(p["w"] for p in members) == 12
            assert len({p["h"] for p in members}) == 1


class TestSanitize:
    def test_garbage_coordinates_clamped(self):
        widgets = [
            {
                "id": "a",
                "position": {"x": 11, "y": "2", "w": 6.7, "h": 0},
                "widget": {"type": "chart", "config": {"type": "bar"}},
            }
        ]
        normalize_dashboard_layout(widgets)
        pos = _pos(widgets, "a")
        assert 0 <= pos["x"] <= GRID_COLUMNS - pos["w"]
        assert pos["w"] >= 3 and pos["h"] >= 1

    def test_missing_position_gets_defaults(self):
        widgets = [{"id": "a", "widget": {"type": "kpi", "config": {}}}]
        normalize_dashboard_layout(widgets)
        pos = _pos(widgets, "a")
        assert pos["w"] >= 2 and pos["h"] >= 1

    def test_never_raises_on_malformed_widget(self):
        widgets = [{"id": "a"}, {"id": "b", "position": None, "widget": None}]
        result = normalize_dashboard_layout(widgets)
        assert result is widgets


class TestPreservation:
    def test_non_position_fields_untouched(self):
        widgets = [
            _w("a", "chart", 0, 0, 5, 5, "bar"),
            _w("b", "chart", 5, 0, 5, 5, "line"),
        ]
        widgets[0]["dataSource"] = {"connectionId": 1, "sql": "SELECT 1"}
        normalize_dashboard_layout(widgets)
        assert [w["id"] for w in widgets] == ["a", "b"]
        a = next(w for w in widgets if w["id"] == "a")
        assert a["dataSource"] == {"connectionId": 1, "sql": "SELECT 1"}


class TestSectionOrdering:
    def test_filter_pulled_to_top_kpis_second(self):
        # Agent emitted filter at the bottom and KPIs in the middle.
        widgets = [
            _w("c1", "chart", 0, 0, 6, 5, "bar"),
            _w("c2", "chart", 6, 0, 6, 5, "line"),
            _w("k1", "kpi", 0, 5, 6, 2),
            _w("k2", "kpi", 6, 5, 6, 2),
            _w("f", "filter", 0, 7, 12, 2),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "f")["y"] == 0
        assert _pos(widgets, "k1")["y"] == _pos(widgets, "k2")["y"] == 2
        assert _pos(widgets, "c1")["y"] == _pos(widgets, "c2")["y"] == 4

    def test_canonical_order_stable(self):
        widgets = _well_formed()
        before = copy.deepcopy([(w["id"], w["position"]) for w in widgets])
        normalize_dashboard_layout(widgets)
        assert [(w["id"], w["position"]) for w in widgets] == before

    def test_array_sorted_into_reading_order(self):
        widgets = [
            _w("table", "table", 0, 10, 12, 5),
            _w("c2", "chart", 6, 0, 6, 5, "line"),
            _w("c1", "chart", 0, 0, 6, 5, "bar"),
        ]
        normalize_dashboard_layout(widgets)
        assert [w["id"] for w in widgets] == ["c1", "c2", "table"]
        positions = [(w["position"]["y"], w["position"]["x"]) for w in widgets]
        assert positions == sorted(positions)


class TestAdaptiveSections:
    """Adaptive storyboard: multiple interleaved section widgets keep their
    emitted order, each on a full-width row, after filter + KPI bands."""

    def _adaptive(self):
        y = 0
        widgets = [_w("f", "filter", 0, y, 12, 2)]
        y += 2
        for i in (1, 2, 3):
            widgets.append(_w(f"k{i}", "kpi", (i - 1) * 4, y, 4, 2))
        y += 2
        widgets += [
            _w("s1", "section", 0, y, 12, 1),
            _w("c1", "chart", 0, y + 1, 6, 5, "line"),
            _w("c2", "chart", 6, y + 1, 6, 5, "bar"),
            _w("s2", "section", 0, y + 6, 12, 1),
            _w("c3", "chart", 0, y + 7, 6, 5, "pie"),
            _w("c4", "chart", 6, y + 7, 6, 5, "bar"),
            _w("s3", "section", 0, y + 12, 12, 1),
            _w("t1", "table", 0, y + 13, 12, 5),
        ]
        return widgets

    def test_interleaved_sections_keep_order(self):
        widgets = self._adaptive()
        normalize_dashboard_layout(widgets)
        ids = [w["id"] for w in widgets]
        assert ids.index("s1") < ids.index("c1") < ids.index("s2")
        assert ids.index("s2") < ids.index("c3") < ids.index("s3")
        assert ids.index("s3") < ids.index("t1")

    def test_sections_full_width_own_row(self):
        widgets = self._adaptive()
        normalize_dashboard_layout(widgets)
        for sid in ("s1", "s2", "s3"):
            pos = _pos(widgets, sid)
            assert pos["x"] == 0 and pos["w"] == 12
            # No other widget shares the section's row.
            same_y = [w for w in widgets if w["position"]["y"] == pos["y"]]
            assert [w["id"] for w in same_y] == [sid]

    def test_filter_and_kpis_precede_sections(self):
        widgets = self._adaptive()
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "f")["y"] == 0
        kpi_y = _pos(widgets, "k1")["y"]
        assert kpi_y == _pos(widgets, "k2")["y"] == _pos(widgets, "k3")["y"]
        assert kpi_y < _pos(widgets, "s1")["y"]

    def test_mid_list_kpi_hoisted_above_first_section(self):
        # Documents the normalizer constraint the prompt encodes: a KPI
        # emitted inside an analysis section is hoisted to the top KPI band.
        widgets = [
            _w("f", "filter", 0, 0, 12, 2),
            _w("k1", "kpi", 0, 2, 6, 2),
            _w("s1", "section", 0, 4, 12, 1),
            _w("c1", "chart", 0, 5, 6, 5, "bar"),
            _w("k2", "kpi", 6, 5, 6, 2),
        ]
        normalize_dashboard_layout(widgets)
        assert _pos(widgets, "k2")["y"] < _pos(widgets, "s1")["y"]
