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

    def test_zero_rows_raises(self):
        result = _qr(["total"], [])
        mapping = {"valueColumn": "total"}
        with pytest.raises(ValueError, match="no rows"):
            transform_kpi(result, mapping)

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

    def test_sparkline_from_all_rows(self):
        result = _qr(["total", "spark"], [(100, 10), (200, 20), (300, 30)])
        mapping = {"valueColumn": "total", "sparklineColumn": "spark"}
        out = transform_kpi(result, mapping)
        assert out["sparkline"] == [10, 20, 30]
        # value should still come from first row only
        assert out["value"] == 100


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
