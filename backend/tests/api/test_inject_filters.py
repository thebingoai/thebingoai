"""Tests for widget filter injection across BigQuery and DuckDB dialects.

Covers the `dialect` arg added for DataPlane DuckDB serving (GAP-5): the same
AST-built conditions must render with the correct placeholder sigil and stay
parseable in each dialect.
"""
import sqlglot

from backend.api.widget_data import inject_filters
from backend.schemas.widget_data import FilterParam


def _f(column, op, value):
    return FilterParam(column=column, op=op, value=value)


# --- BigQuery (default) path unchanged -------------------------------------

def test_bigquery_emits_psycopg_placeholders():
    # The BQ path rewrites placeholders to psycopg2 `%(name)s` (bound by the
    # source-DB connector), which is intentionally not re-parseable SQL.
    sql = "SELECT region, SUM(revenue) AS r FROM `csv_1` GROUP BY region"
    out, params = inject_filters(sql, [_f("region", "eq", "EMEA")])
    assert "%(_f0)s" in out
    assert "`region` = %(_f0)s" in out
    assert params == {"_f0": "EMEA"}


def test_bigquery_in_operator_multikey():
    sql = "SELECT * FROM `csv_1`"
    out, params = inject_filters(sql, [_f("region", "in", ["EMEA", "APAC"])])
    assert "%(_f0_0)s" in out and "%(_f0_1)s" in out
    assert params == {"_f0_0": "EMEA", "_f0_1": "APAC"}


# --- DuckDB path -----------------------------------------------------------

def test_duckdb_emits_dollar_placeholders():
    sql = "SELECT region, SUM(revenue) AS r FROM csv_1 GROUP BY region"
    out, params = inject_filters(sql, [_f("region", "eq", "EMEA")], dialect="duckdb")
    assert "$_f0" in out
    assert "%(_f0)s" not in out
    assert params == {"_f0": "EMEA"}
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_in_operator_multikey():
    sql = "SELECT * FROM csv_1"
    out, params = inject_filters(sql, [_f("region", "in", ["EMEA", "APAC"])], dialect="duckdb")
    assert "$_f0_0" in out and "$_f0_1" in out
    assert params == {"_f0_0": "EMEA", "_f0_1": "APAC"}
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_duckdb_date_coercion_renders_cast():
    # When the column is a date-like type, the filter wraps it so a YYYY-MM-DD
    # string compares as a DATE. DuckDB renders this as CAST(... AS DATE).
    sql = "SELECT * FROM csv_1"
    ctx = {"dimensions": {"ts": {"column": "ts", "type": "TIMESTAMP"}}}
    out, params = inject_filters(
        sql, [_f("ts", "gte", "2024-01-01")], data_context=ctx, dialect="duckdb"
    )
    assert "CAST" in out.upper()
    assert "$_f0" in out
    sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_no_filters_returns_sql_unchanged():
    sql = "SELECT * FROM csv_1"
    out, params = inject_filters(sql, [], dialect="duckdb")
    assert out == sql
    assert params == {}
