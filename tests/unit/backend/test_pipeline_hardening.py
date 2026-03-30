"""Unit tests for Phase 5 — Pipeline Hardening.

Tests CTE stripping, SQL validation improvements, build_schema_summary formats,
case-insensitive column matching, KPI empty state, and better error messages.
"""
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.connectors.base import QueryResult
from backend.services.schema_utils import build_schema_summary, extract_table_names
from backend.services.widget_transform import (
    _find_column,
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


def _make_schema(tables: dict, relationships=None):
    """Build a schema JSON with tables dict and optional relationships."""
    schema = {"tables": []}
    for name, cols in tables.items():
        schema["tables"].append({
            "name": name,
            "row_count": 100,
            "columns": [{"name": c, "data_type": "text"} for c in cols],
        })
    if relationships:
        schema["relationships"] = relationships
    return schema


# ---------------------------------------------------------------------------
# TestCteStripping — CTE names excluded from table validation
# ---------------------------------------------------------------------------

class TestCteStripping:
    """Verify CTE names are excluded from table-not-found warnings."""

    def _run_validation(self, sql, schema_json, widget_id="w1"):
        from backend.agents.dashboard_tools import _validate_widget_sql_schema
        widgets = [{
            "id": widget_id,
            "position": {"x": 0, "y": 0, "w": 6, "h": 4},
            "widget": {"type": "chart", "config": {}},
            "dataSource": {
                "connectionId": 1,
                "sql": sql,
                "mapping": {"type": "chart", "labelColumn": "x", "datasetColumns": []},
            },
        }]
        with patch("backend.services.schema_discovery.load_schema_file", return_value=schema_json):
            return _validate_widget_sql_schema(widgets)

    def test_simple_cte_no_warning(self):
        schema = _make_schema({"orders": ["id", "amount"]})
        sql = "WITH totals AS (SELECT id, SUM(amount) AS total FROM orders GROUP BY id) SELECT * FROM totals"
        warnings = self._run_validation(sql, schema)
        # "totals" is a CTE, should not trigger "table not found"
        assert not any("totals" in w.lower() for w in warnings)

    def test_nested_cte_no_warning(self):
        schema = _make_schema({"orders": ["id", "amount", "status"]})
        sql = (
            "WITH active AS (SELECT * FROM orders WHERE status = 'active'), "
            "summary AS (SELECT COUNT(*) AS cnt FROM active) "
            "SELECT * FROM summary"
        )
        warnings = self._run_validation(sql, schema)
        assert not any("active" in w.lower() or "summary" in w.lower() for w in warnings)

    def test_recursive_cte_no_warning(self):
        schema = _make_schema({"employees": ["id", "name", "manager_id"]})
        sql = (
            "WITH RECURSIVE hierarchy AS ("
            "SELECT id, name FROM employees WHERE manager_id IS NULL "
            "UNION ALL SELECT e.id, e.name FROM employees e JOIN hierarchy h ON e.manager_id = h.id"
            ") SELECT * FROM hierarchy"
        )
        warnings = self._run_validation(sql, schema)
        assert not any("hierarchy" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# TestSqlValidation — validate all tables, window/CASE keywords
# ---------------------------------------------------------------------------

class TestSqlValidation:
    """Verify SQL validation catches invalid tables and ignores SQL keywords."""

    def _run_validation(self, sql, schema_json, widget_id="w1"):
        from backend.agents.dashboard_tools import _validate_widget_sql_schema
        widgets = [{
            "id": widget_id,
            "position": {"x": 0, "y": 0, "w": 6, "h": 4},
            "widget": {"type": "chart", "config": {}},
            "dataSource": {
                "connectionId": 1,
                "sql": sql,
                "mapping": {"type": "chart", "labelColumn": "x", "datasetColumns": []},
            },
        }]
        with patch("backend.services.schema_discovery.load_schema_file", return_value=schema_json):
            return _validate_widget_sql_schema(widgets)

    def test_invalid_table_reference(self):
        schema = _make_schema({"orders": ["id", "amount"]})
        sql = "SELECT * FROM nonexistent_table"
        warnings = self._run_validation(sql, schema)
        assert any("nonexistent_table" in w for w in warnings)

    def test_validates_all_joined_tables(self):
        """Previously only the first table was validated. Now all joined tables are checked."""
        schema = _make_schema({"orders": ["id", "customer_id"]})
        sql = "SELECT * FROM orders JOIN fake_table ON orders.id = fake_table.order_id"
        warnings = self._run_validation(sql, schema)
        assert any("fake_table" in w for w in warnings)

    def test_window_functions_no_false_positive(self):
        schema = _make_schema({"sales": ["id", "amount", "region"]})
        sql = (
            "SELECT id, amount, ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC) AS rn "
            "FROM sales"
        )
        warnings = self._run_validation(sql, schema)
        # "row_number", "over", "partition" should not be flagged as missing columns
        assert not any("row_number" in w.lower() or "partition" in w.lower() for w in warnings)

    def test_case_expressions_no_false_positive(self):
        schema = _make_schema({"orders": ["id", "amount", "status"]})
        sql = (
            "SELECT id, CASE WHEN amount > 100 THEN 'high' ELSE 'low' END AS tier "
            "FROM orders"
        )
        warnings = self._run_validation(sql, schema)
        # CASE, WHEN, THEN, ELSE, END should not be flagged
        assert not any(kw in w.lower() for w in warnings for kw in ["case", "when", "then", "else", "end"])


# ---------------------------------------------------------------------------
# TestSqlFixSecondAttempt — sample data + baseJoin context in fix prompt
# ---------------------------------------------------------------------------

class TestSqlFixSecondAttempt:
    """Verify _attempt_sql_fix includes sample data and baseJoin in prompt."""

    @pytest.mark.asyncio
    async def test_second_attempt_with_sample_data(self):
        from backend.agents.dashboard_tools import _attempt_sql_fix

        connection = MagicMock()
        connection.id = 1
        connection.db_type = "postgresql"

        data_context = {
            "baseJoin": {"from": "orders", "to": "customers", "on": "customer_id"},
        }
        sample_data = "\nTable 'orders' sample:\n  Columns: ['id', 'amount']\n  [1, 100]\n"

        mock_provider = MagicMock()
        mock_provider.chat = AsyncMock(return_value=json.dumps({
            "suggested_sql": "SELECT * FROM orders",
            "explanation": "Fixed table name",
        }))

        with patch("backend.services.schema_discovery.load_schema_file", side_effect=FileNotFoundError), \
             patch("backend.agents.dashboard_tools.get_connector_registration", return_value=None), \
             patch("backend.llm.factory.get_provider", return_value=mock_provider):

            result = await _attempt_sql_fix(
                sql="SELECT * FROM ordrs",
                error_message="table 'ordrs' does not exist",
                connection=connection,
                mapping={"type": "chart"},
                widget_id="w1",
                data_context=data_context,
                sample_data=sample_data,
            )

        assert result == "SELECT * FROM orders"
        # Verify the prompt included baseJoin and sample data
        prompt_used = mock_provider.chat.call_args[0][0][0]["content"]
        assert "baseJoin" in prompt_used or "base join" in prompt_used.lower()
        assert "orders" in prompt_used
        assert "sample" in prompt_used.lower()


# ---------------------------------------------------------------------------
# TestBuildSchemaSummary — relationship format handling
# ---------------------------------------------------------------------------

class TestBuildSchemaSummary:
    def test_dot_notation_format(self):
        """Format A: {from: 'table.column', to: 'table.column'}."""
        schema = _make_schema(
            {"orders": ["id", "customer_id"], "customers": ["id", "name"]},
            relationships=[{"from": "orders.customer_id", "to": "customers.id"}],
        )
        summary = build_schema_summary(schema, {"orders", "customers"})
        assert "orders.customer_id -> customers.id" in summary

    def test_separate_fields_format(self):
        """Format B: {from_table, from_column, to_table, to_column}."""
        schema = _make_schema(
            {"orders": ["id", "customer_id"], "customers": ["id", "name"]},
            relationships=[{
                "from_table": "orders",
                "from_column": "customer_id",
                "to_table": "customers",
                "to_column": "id",
            }],
        )
        summary = build_schema_summary(schema, {"orders", "customers"})
        assert "orders.customer_id -> customers.id" in summary


# ---------------------------------------------------------------------------
# TestCaseInsensitiveColumnMatching
# ---------------------------------------------------------------------------

class TestCaseInsensitiveColumnMatching:
    def test_exact_match(self):
        assert _find_column("revenue", ["id", "revenue", "cost"]) == 1

    def test_case_insensitive_match(self):
        """'Revenue' matches 'revenue' in result columns."""
        assert _find_column("Revenue", ["id", "revenue", "cost"]) == 1

    def test_case_insensitive_reverse(self):
        """'revenue' matches 'Revenue' in result columns."""
        assert _find_column("revenue", ["id", "Revenue", "cost"]) == 1

    def test_chart_case_insensitive(self):
        result = _qr(["Month", "Sales"], [("Jan", 100)])
        mapping = {
            "labelColumn": "month",  # lowercase vs uppercase in result
            "datasetColumns": [{"column": "sales", "label": "S"}],
        }
        out = transform_chart(result, mapping)
        assert out["data"]["labels"] == ["Jan"]
        assert out["data"]["datasets"][0]["data"] == [100]

    def test_kpi_case_insensitive(self):
        result = _qr(["Total_Revenue"], [(42,)])
        mapping = {"valueColumn": "total_revenue"}
        out = transform_kpi(result, mapping)
        assert out["value"] == 42

    def test_table_case_insensitive(self):
        result = _qr(["ID", "Name"], [(1, "Alice")])
        mapping = {"columnConfig": [{"column": "id", "label": "ID"}, {"column": "name", "label": "Name"}]}
        out = transform_table(result, mapping)
        assert out["rows"][0]["id"] == 1
        assert out["rows"][0]["name"] == "Alice"


# ---------------------------------------------------------------------------
# TestKpiEmptyState — 0 rows returns null, not ValueError
# ---------------------------------------------------------------------------

class TestKpiEmptyState:
    def test_zero_rows_returns_null(self):
        result = _qr(["total"], [])
        mapping = {"valueColumn": "total"}
        out = transform_kpi(result, mapping)
        assert out == {"value": None}

    def test_zero_rows_with_optional_columns(self):
        result = _qr(["total", "trend", "sparkx", "sparky"], [])
        mapping = {
            "valueColumn": "total",
            "trendValueColumn": "trend",
            "sparklineXColumn": "sparkx",
            "sparklineYColumn": "sparky",
        }
        out = transform_kpi(result, mapping)
        assert out == {"value": None}


# ---------------------------------------------------------------------------
# TestErrorMessages — field name and closest match in errors
# ---------------------------------------------------------------------------

class TestErrorMessages:
    def test_includes_field_name_and_closest_match(self):
        with pytest.raises(ValueError) as exc_info:
            _find_column("revnue", ["id", "revenue", "cost"], "valueColumn")
        msg = str(exc_info.value)
        assert "mapping field: valueColumn" in msg
        assert "Did you mean 'revenue'" in msg
        assert "Available columns:" in msg

    def test_chart_error_includes_field_name(self):
        result = _qr(["month", "sales"], [("Jan", 100)])
        mapping = {
            "labelColumn": "mnth",
            "datasetColumns": [{"column": "sales"}],
        }
        with pytest.raises(ValueError) as exc_info:
            transform_chart(result, mapping)
        msg = str(exc_info.value)
        assert "labelColumn" in msg
        assert "Did you mean 'month'" in msg

    def test_table_error_includes_field_name(self):
        result = _qr(["id", "name"], [(1, "Alice")])
        mapping = {"columnConfig": [{"column": "nme"}]}
        with pytest.raises(ValueError) as exc_info:
            transform_table(result, mapping)
        msg = str(exc_info.value)
        assert "columnConfig" in msg
        assert "Did you mean 'name'" in msg

    def test_no_close_match_still_shows_available(self):
        with pytest.raises(ValueError) as exc_info:
            _find_column("zzzzz", ["id", "revenue", "cost"])
        msg = str(exc_info.value)
        assert "Available columns:" in msg
        assert "Did you mean" not in msg
