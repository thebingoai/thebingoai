"""Unit tests for backend.services.widget_transform — pure function tests."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from backend.connectors.base import QueryResult
from backend.services.widget_transform import (
    _to_json_safe,
    transform_chart,
    transform_kpi,
    transform_table,
    transform_widget_data,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _qr(columns, rows):
    """Shorthand to build a QueryResult."""
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_time_ms=1.0,
    )


# ---------------------------------------------------------------------------
# TestToJsonSafe
# ---------------------------------------------------------------------------

class TestToJsonSafe:
    def test_decimal_converted_to_float(self):
        assert _to_json_safe(Decimal("3.14")) == 3.14
        assert isinstance(_to_json_safe(Decimal("10")), float)

    def test_datetime_converted_to_isoformat(self):
        dt = datetime(2025, 6, 15, 10, 30, 0)
        assert _to_json_safe(dt) == "2025-06-15T10:30:00"

    def test_date_converted_to_isoformat(self):
        d = date(2025, 6, 15)
        assert _to_json_safe(d) == "2025-06-15"

    def test_string_passthrough(self):
        assert _to_json_safe("hello") == "hello"

    def test_none_passthrough(self):
        assert _to_json_safe(None) is None


# ---------------------------------------------------------------------------
# TestTransformChart
# ---------------------------------------------------------------------------

class TestTransformChart:
    def test_basic_labels_and_single_dataset(self):
        result = _qr(["month", "sales"], [("Jan", 100), ("Feb", 200)])
        mapping = {
            "labelColumn": "month",
            "datasetColumns": [{"column": "sales", "label": "Monthly Sales"}],
        }
        out = transform_chart(result, mapping)

        assert out["data"]["labels"] == ["Jan", "Feb"]
        assert len(out["data"]["datasets"]) == 1
        assert out["data"]["datasets"][0]["label"] == "Monthly Sales"
        assert out["data"]["datasets"][0]["data"] == [100, 200]

    def test_multiple_datasets(self):
        result = _qr(
            ["month", "sales", "returns"],
            [("Jan", 100, 5), ("Feb", 200, 10)],
        )
        mapping = {
            "labelColumn": "month",
            "datasetColumns": [
                {"column": "sales", "label": "Sales"},
                {"column": "returns", "label": "Returns"},
            ],
        }
        out = transform_chart(result, mapping)

        assert len(out["data"]["datasets"]) == 2
        assert out["data"]["datasets"][0]["data"] == [100, 200]
        assert out["data"]["datasets"][1]["data"] == [5, 10]

    def test_missing_label_column_raises(self):
        result = _qr(["month", "sales"], [("Jan", 100)])
        mapping = {
            "labelColumn": "nonexistent",
            "datasetColumns": [{"column": "sales"}],
        }
        with pytest.raises(ValueError, match="nonexistent"):
            transform_chart(result, mapping)

    def test_missing_dataset_column_raises(self):
        result = _qr(["month", "sales"], [("Jan", 100)])
        mapping = {
            "labelColumn": "month",
            "datasetColumns": [{"column": "nonexistent"}],
        }
        with pytest.raises(ValueError, match="nonexistent"):
            transform_chart(result, mapping)

    def test_passthrough_styling_keys(self):
        result = _qr(["x", "y"], [("a", 1)])
        mapping = {
            "labelColumn": "x",
            "datasetColumns": [
                {
                    "column": "y",
                    "label": "Y",
                    "backgroundColor": "red",
                    "borderColor": "blue",
                    "borderWidth": 2,
                    "fill": True,
                    "tension": 0.4,
                    "pointRadius": 3,
                },
            ],
        }
        out = transform_chart(result, mapping)
        ds = out["data"]["datasets"][0]
        assert ds["backgroundColor"] == "red"
        assert ds["borderColor"] == "blue"
        assert ds["borderWidth"] == 2
        assert ds["fill"] is True
        assert ds["tension"] == 0.4
        assert ds["pointRadius"] == 3

    def test_empty_rows(self):
        result = _qr(["month", "sales"], [])
        mapping = {
            "labelColumn": "month",
            "datasetColumns": [{"column": "sales", "label": "Sales"}],
        }
        out = transform_chart(result, mapping)
        assert out["data"]["labels"] == []
        assert out["data"]["datasets"][0]["data"] == []

    def test_decimal_values_in_data(self):
        result = _qr(["x", "y"], [("a", Decimal("9.99")), ("b", Decimal("0.01"))])
        mapping = {
            "labelColumn": "x",
            "datasetColumns": [{"column": "y", "label": "Y"}],
        }
        out = transform_chart(result, mapping)
        assert out["data"]["datasets"][0]["data"] == [9.99, 0.01]

    def test_label_defaults_to_column_name(self):
        result = _qr(["x", "y"], [("a", 1)])
        mapping = {
            "labelColumn": "x",
            "datasetColumns": [{"column": "y"}],  # no "label" key
        }
        out = transform_chart(result, mapping)
        assert out["data"]["datasets"][0]["label"] == "y"


# ---------------------------------------------------------------------------
# TestTransformKpi
# ---------------------------------------------------------------------------

class TestTransformKpi:
    def test_basic_value_extraction(self):
        result = _qr(["total"], [(42,)])
        mapping = {"valueColumn": "total"}
        out = transform_kpi(result, mapping)
        assert out["value"] == 42

    def test_missing_value_column_raises(self):
        result = _qr(["total"], [(42,)])
        mapping = {"valueColumn": "nonexistent"}
        with pytest.raises(ValueError, match="nonexistent"):
            transform_kpi(result, mapping)

    def test_zero_rows_returns_null(self):
        result = _qr(["total"], [])
        mapping = {"valueColumn": "total"}
        out = transform_kpi(result, mapping)
        assert out == {"value": None}

    def test_trend_up_positive(self):
        result = _qr(["total", "change"], [(100, 15)])
        mapping = {"valueColumn": "total", "trendValueColumn": "change"}
        out = transform_kpi(result, mapping)
        assert out["trend"]["direction"] == "up"
        assert out["trend"]["value"] == 15

    def test_trend_down_negative(self):
        result = _qr(["total", "change"], [(100, -5)])
        mapping = {"valueColumn": "total", "trendValueColumn": "change"}
        out = transform_kpi(result, mapping)
        assert out["trend"]["direction"] == "down"
        assert out["trend"]["value"] == -5

    def test_trend_neutral_zero(self):
        result = _qr(["total", "change"], [(100, 0)])
        mapping = {"valueColumn": "total", "trendValueColumn": "change"}
        out = transform_kpi(result, mapping)
        assert out["trend"]["direction"] == "neutral"
        assert out["trend"]["value"] == 0

    def test_trend_non_numeric_is_neutral(self):
        result = _qr(["total", "change"], [(100, "N/A")])
        mapping = {"valueColumn": "total", "trendValueColumn": "change"}
        out = transform_kpi(result, mapping)
        assert out["trend"]["direction"] == "neutral"
        assert out["trend"]["value"] == "N/A"

    def test_multi_row_without_aggregation_sums(self):
        # Sparkline is computed frontend-side (widgetTransform.ts), not by transform_kpi.
        # Here we pin the backend contract: with no explicit aggregation a MULTI-row
        # result is summed. Showing row 0 is what made a 15k-row KPI render one cell.
        result = _qr(["total", "spark"], [(100, 10), (200, 20), (300, 30)])
        mapping = {"valueColumn": "total", "sparklineYColumn": "spark"}
        out = transform_kpi(result, mapping)
        assert out["value"] == 600

    def test_single_row_without_aggregation_keeps_first(self):
        """The multi-row rule is deliberately narrow: one row means one reading,
        so single-row KPIs are untouched (the blanket sum-default was reverted
        in 5dbd4e7 precisely because it reinterpreted these)."""
        result = _qr(["total"], [(100,)])
        out = transform_kpi(result, {"valueColumn": "total"})
        assert out["value"] == 100

    def test_explicit_first_is_never_overridden(self):
        """An author who chose "first" gets row 0 even on a multi-row result."""
        result = _qr(["total"], [(100,), (200,), (300,)])
        out = transform_kpi(result, {"valueColumn": "total", "aggregation": "first"})
        assert out["value"] == 100

    def test_count_distinct_is_implemented(self):
        """countDistinct is offered by the editor and the agent params_doc; before
        delegating to _aggregate_values it fell through to row 0."""
        result = _qr(["plan"], [(10,), (20,), (10,), (20,), (30,)])
        out = transform_kpi(result, {"valueColumn": "plan", "aggregation": "countDistinct"})
        assert out["value"] == 3

    def test_count_counts_non_null_values_of_any_type(self):
        """Delegating to _aggregate_values changes `count` from numeric-only to
        every non-null cell — the same rule the frontend transform applies."""
        result = _qr(["label"], [("a",), ("b",), (None,), ("c",)])
        out = transform_kpi(result, {"valueColumn": "label", "aggregation": "count"})
        assert out["value"] == 3

    def test_non_numeric_column_falls_back_to_first_row(self):
        """A text column summed has no numeric values — keep showing row 0
        rather than rendering nothing."""
        result = _qr(["name"], [("alpha",), ("beta",)])
        out = transform_kpi(result, {"valueColumn": "name", "aggregation": "sum"})
        assert out["value"] == "alpha"

    def test_null_aggregation_is_treated_as_absent(self):
        """Mappings can persist an explicit null; it must not be read as an
        unrecognized aggregation (which would mean row 0)."""
        result = _qr(["total"], [(100,), (200,)])
        out = transform_kpi(result, {"valueColumn": "total", "aggregation": None})
        assert out["value"] == 300

    def test_unknown_aggregation_is_treated_as_absent(self):
        """`_aggregate_values` answers "first" for anything it doesn't know, so a
        stored `"average"` would re-create the row-0 headline. Unknown values
        take the same multi-row default as an absent one."""
        result = _qr(["total"], [(100,), (200,)])
        out = transform_kpi(result, {"valueColumn": "total", "aggregation": "average"})
        assert out["value"] == 300


# ---------------------------------------------------------------------------
# TestTransformTable
# ---------------------------------------------------------------------------

class TestTransformTable:
    def test_basic_columns_and_rows(self):
        result = _qr(["id", "name", "age"], [(1, "Alice", 30), (2, "Bob", 25)])
        mapping = {
            "columnConfig": [
                {"column": "id", "label": "ID"},
                {"column": "name", "label": "Name"},
            ],
        }
        out = transform_table(result, mapping)

        assert len(out["columns"]) == 2
        assert out["columns"][0] == {"key": "id", "label": "ID"}
        assert out["columns"][1] == {"key": "name", "label": "Name"}

        assert len(out["rows"]) == 2
        assert out["rows"][0] == {"id": 1, "name": "Alice"}
        assert out["rows"][1] == {"id": 2, "name": "Bob"}

    def test_missing_column_raises(self):
        result = _qr(["id", "name"], [(1, "Alice")])
        mapping = {"columnConfig": [{"column": "nonexistent"}]}
        with pytest.raises(ValueError, match="nonexistent"):
            transform_table(result, mapping)

    def test_sortable_and_format_passthrough(self):
        result = _qr(["price"], [(Decimal("9.99"),)])
        mapping = {
            "columnConfig": [
                {"column": "price", "label": "Price", "sortable": True, "format": "currency"},
            ],
        }
        out = transform_table(result, mapping)
        col = out["columns"][0]
        assert col["sortable"] is True
        assert col["format"] == "currency"

    def test_empty_rows_produce_empty_list(self):
        result = _qr(["id", "name"], [])
        mapping = {
            "columnConfig": [
                {"column": "id", "label": "ID"},
                {"column": "name", "label": "Name"},
            ],
        }
        out = transform_table(result, mapping)
        assert out["rows"] == []
        assert len(out["columns"]) == 2

    def test_label_defaults_to_column_name(self):
        result = _qr(["status"], [("active",)])
        mapping = {"columnConfig": [{"column": "status"}]}  # no "label"
        out = transform_table(result, mapping)
        assert out["columns"][0]["label"] == "status"


# ---------------------------------------------------------------------------
# TestTransformWidgetData
# ---------------------------------------------------------------------------

class TestTransformWidgetData:
    def test_dispatches_to_chart(self):
        result = _qr(["x", "y"], [("a", 1)])
        mapping = {
            "type": "chart",
            "labelColumn": "x",
            "datasetColumns": [{"column": "y"}],
        }
        out = transform_widget_data(result, mapping)
        assert "data" in out
        assert "labels" in out["data"]
        assert "datasets" in out["data"]

    def test_dispatches_to_kpi(self):
        result = _qr(["total"], [(99,)])
        mapping = {"type": "kpi", "valueColumn": "total"}
        out = transform_widget_data(result, mapping)
        assert out["value"] == 99

    def test_dispatches_to_table(self):
        result = _qr(["col1"], [("val",)])
        mapping = {
            "type": "table",
            "columnConfig": [{"column": "col1", "label": "Col 1"}],
        }
        out = transform_widget_data(result, mapping)
        assert "columns" in out
        assert "rows" in out

    def test_unknown_type_raises(self):
        result = _qr(["x"], [("a",)])
        mapping = {"type": "unknown_widget"}
        with pytest.raises(ValueError, match="Unsupported mapping type"):
            transform_widget_data(result, mapping)


class TestTruncatedAndStructuredValues:
    """Guards on the client-side KPI aggregate: it must refuse a capped result
    and must not crash on JSON/array cells."""

    def test_truncated_result_refuses_to_aggregate(self):
        """settings.max_query_rows clamps every connector and the DuckDB runner
        before transform_kpi sees the rows, so summing here would total only the
        prefix and return it as a correct headline."""
        result = QueryResult(columns=["total"], rows=[(100,), (200,)], row_count=2,
                             execution_time_ms=1.0, truncated=True)
        with pytest.raises(ValueError, match="truncated"):
            transform_kpi(result, {"valueColumn": "total", "aggregation": "sum"})

    def test_truncated_result_still_allows_first(self):
        """"first" reads row 0, which the cap doesn't change."""
        result = QueryResult(columns=["total"], rows=[(100,), (200,)], row_count=2,
                             execution_time_ms=1.0, truncated=True)
        out = transform_kpi(result, {"valueColumn": "total", "aggregation": "first"})
        assert out["value"] == 100

    def test_count_distinct_handles_json_and_array_cells(self):
        """JSON / JSONB / STRUCT / array columns arrive as dict or list — both
        unhashable, so set() raised TypeError and surfaced as a 500."""
        result = _qr(["payload"], [
            ({"a": 1},), ({"a": 1},), ([1, 2],), ([1, 2],), (None,), ("x",),
        ])
        out = transform_kpi(result, {"valueColumn": "payload",
                                     "aggregation": "countDistinct"})
        assert out["value"] == 3

    def test_count_distinct_keeps_a_dict_apart_from_its_own_json_text(self):
        """Structured cells are keyed by canonical text so duplicates collapse;
        keying them by text alone made a dict indistinguishable from a string
        column holding the same JSON."""
        result = _qr(["payload"], [({"a": 1},), ('{"a": 1}',)])
        out = transform_kpi(result, {"valueColumn": "payload",
                                     "aggregation": "countDistinct"})
        assert out["value"] == 2
