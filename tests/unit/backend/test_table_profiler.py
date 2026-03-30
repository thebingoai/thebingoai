"""Tests for backend.services.table_profiler — shared profiling logic."""
import pytest
from unittest.mock import MagicMock

from backend.connectors.base import QueryResult
from backend.services.table_profiler import profile_table, MAX_COLUMNS


def _mock_connector(*results):
    """Create a mock connector that returns successive QueryResults."""
    connector = MagicMock()
    if len(results) == 1:
        connector.execute_query.return_value = results[0]
    else:
        connector.execute_query.side_effect = list(results)
    return connector


def _qr(columns, rows):
    return QueryResult(columns=columns, rows=rows, row_count=len(rows), execution_time_ms=1.0)


class TestProfileTable:
    """Tests for profile_table function."""

    def test_numeric_columns_return_min_max_avg(self):
        # Numeric query returns: MIN, MAX, AVG, NULL_COUNT per column
        result = _qr(["min_a", "max_a", "avg_a", "null_a"], [(10, 100, 55.0, 0)])
        connector = _mock_connector(result)

        columns = [{"name": "amount", "type": "numeric"}]
        out = profile_table(connector, "orders", "public", columns, 100)

        assert out["columns"]["amount"]["type"] == "numeric"
        assert out["columns"]["amount"]["min"] == 10
        assert out["columns"]["amount"]["max"] == 100
        assert out["columns"]["amount"]["avg"] == 55.0
        assert out["columns"]["amount"]["null_count"] == 0

    def test_date_columns_return_min_max(self):
        result = _qr(["min_d", "max_d", "null_d"], [("2023-01-01", "2025-12-31", 5)])
        connector = _mock_connector(result)

        columns = [{"name": "created_at", "type": "date"}]
        out = profile_table(connector, "events", "public", columns, 50)

        assert out["columns"]["created_at"]["type"] == "date"
        assert out["columns"]["created_at"]["min"] == "2023-01-01"
        assert out["columns"]["created_at"]["max"] == "2025-12-31"

    def test_categorical_columns_return_distinct_count(self):
        # Categorical query: COUNT(DISTINCT), NULL_COUNT
        result = _qr(["d", "n"], [(8, 2)])
        connector = _mock_connector(result)

        columns = [{"name": "region", "type": "varchar"}]
        out = profile_table(connector, "orders", "public", columns, 100)

        assert out["columns"]["region"]["type"] == "categorical"
        assert out["columns"]["region"]["distinct_count"] == 8

    def test_top_values_fetched_when_cardinality_under_threshold(self):
        # First call: categorical stats (distinct_count=5)
        cat_result = _qr(["d", "n"], [(5, 0)])
        # Second call: top values
        top_result = _qr(["region", "count"], [("US", 40), ("UK", 30), ("EU", 20)])
        connector = _mock_connector(cat_result, top_result)

        columns = [{"name": "region", "type": "varchar"}]
        out = profile_table(connector, "orders", "public", columns, 100)

        assert "top_values" in out["columns"]["region"]
        assert out["columns"]["region"]["top_values"] == ["US", "UK", "EU"]

    def test_top_values_skipped_for_high_cardinality(self):
        cat_result = _qr(["d", "n"], [(200, 0)])
        connector = _mock_connector(cat_result)

        columns = [{"name": "email", "type": "text"}]
        out = profile_table(connector, "users", "public", columns, 1000)

        assert "top_values" not in out["columns"]["email"]
        # Only one query should have been made (no top values query)
        assert connector.execute_query.call_count == 1

    def test_query_failure_per_column_type_is_graceful(self):
        connector = MagicMock()
        connector.execute_query.side_effect = RuntimeError("DB error")

        columns = [
            {"name": "amount", "type": "numeric"},
            {"name": "date", "type": "date"},
            {"name": "region", "type": "varchar"},
        ]
        out = profile_table(connector, "orders", "public", columns, 100)

        # All columns should still be in result, with error keys
        assert "error" in out["columns"]["amount"]
        assert "error" in out["columns"]["date"]
        assert "error" in out["columns"]["region"]

    def test_column_cap_at_30(self):
        columns = [{"name": f"col_{i}", "type": "text"} for i in range(50)]
        cat_result = _qr(
            [f"d{i}" for i in range(60)],
            [tuple([1, 0] * 30)]  # pairs of distinct_count, null_count
        )
        connector = _mock_connector(cat_result)

        out = profile_table(connector, "wide_table", "public", columns, 100)

        # Should only profile first 30 columns
        assert len(out["columns"]) == MAX_COLUMNS

    def test_mysql_quoting_uses_backticks(self):
        result = _qr(["d", "n"], [(3, 0)])
        connector = _mock_connector(result)

        columns = [{"name": "status", "type": "varchar"}]
        profile_table(connector, "orders", "public", columns, 10, db_type="mysql")

        sql = connector.execute_query.call_args[0][0]
        assert "`status`" in sql
        assert "`public`" in sql

    def test_postgres_quoting_uses_double_quotes(self):
        result = _qr(["d", "n"], [(3, 0)])
        connector = _mock_connector(result)

        columns = [{"name": "status", "type": "varchar"}]
        profile_table(connector, "orders", "public", columns, 10, db_type="postgres")

        sql = connector.execute_query.call_args[0][0]
        assert '"status"' in sql

    def test_dataset_uses_unqualified_table_name(self):
        result = _qr(["d", "n"], [(3, 0)])
        connector = _mock_connector(result)

        columns = [{"name": "col", "type": "varchar"}]
        profile_table(connector, "data", None, columns, 10, is_dataset=True)

        sql = connector.execute_query.call_args[0][0]
        assert '"data"' in sql
        # Should NOT have schema prefix
        assert "." not in sql.split("FROM")[1].split("WHERE")[0].strip().strip('"')

    def test_empty_table_returns_zero_row_count(self):
        connector = MagicMock()
        connector.execute_query.return_value = _qr([], [])

        columns = []
        out = profile_table(connector, "empty", "public", columns, 0)

        assert out["table_name"] == "empty"
        assert out["row_count"] == 0
        assert out["columns"] == {}

    def test_mixed_column_types(self):
        """Profile a table with numeric, date, and text columns in one call."""
        num_result = _qr(["mn", "mx", "av", "nl"], [(1, 100, 50.0, 0)])
        date_result = _qr(["mn", "mx", "nl"], [("2024-01-01", "2024-12-31", 0)])
        cat_result = _qr(["d", "n"], [(5, 0)])
        top_result = _qr(["v", "c"], [("A", 10), ("B", 5)])

        connector = _mock_connector(num_result, date_result, cat_result, top_result)

        columns = [
            {"name": "amount", "type": "numeric"},
            {"name": "created_at", "type": "timestamp"},
            {"name": "status", "type": "varchar"},
        ]
        out = profile_table(connector, "orders", "public", columns, 100)

        assert out["columns"]["amount"]["type"] == "numeric"
        assert out["columns"]["created_at"]["type"] == "date"
        assert out["columns"]["status"]["type"] == "categorical"
