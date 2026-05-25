import pytest

import sqlglot

from backend.utils.sql_refs import (
    extract_table_refs,
    rewrite_table_refs,
    can_parse,
    transpile_bq_to_duckdb,
    UntranspilableSQLError,
)


def _assert_valid_duckdb(sql: str) -> None:
    """Raise if *sql* is not parseable as DuckDB."""
    sqlglot.parse_one(sql, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)


def test_extract_single_table():
    result = extract_table_refs("SELECT * FROM foo")
    assert result == ["foo"]


def test_extract_multiple_tables():
    result = extract_table_refs("SELECT * FROM foo JOIN bar ON foo.id = bar.id")
    assert result == ["bar", "foo"]


def test_extract_unparseable():
    result = extract_table_refs("garbage that can't parse")
    assert result == []


def test_rewrite_single_table():
    result_sql, success = rewrite_table_refs("SELECT * FROM legacy", {"legacy": "new_table"})
    assert success is True
    assert "new_table" in result_sql


def test_rewrite_with_cte():
    sql = "WITH cte AS (SELECT * FROM legacy) SELECT * FROM cte"
    result_sql, success = rewrite_table_refs(sql, {"legacy": "new_table"})
    assert success is True
    assert "new_table" in result_sql


def test_rewrite_case_insensitive():
    result_sql, success = rewrite_table_refs("SELECT * FROM legacy", {"LEGACY": "new"})
    assert success is True
    assert "new" in result_sql


def test_rewrite_unparseable():
    bad_sql = "SELECT @@@;###"
    result_sql, success = rewrite_table_refs(bad_sql, {"a": "b"})
    assert success is False
    assert result_sql == bad_sql


def test_can_parse_valid():
    assert can_parse("SELECT 1") is True


def test_can_parse_invalid():
    assert can_parse("NOT SQL AT ALL !!!") is False


# ---------------------------------------------------------------------------
# BQ → DuckDB transpile corpus (GAP-6)
# ---------------------------------------------------------------------------

def test_transpile_backticks_become_double_quotes():
    out = transpile_bq_to_duckdb("SELECT `col` FROM `tbl`")
    assert "`" not in out
    _assert_valid_duckdb(out)


def test_transpile_date_trunc_reorders_args():
    out = transpile_bq_to_duckdb("SELECT DATE_TRUNC(d, DAY) FROM t")
    # BigQuery DATE_TRUNC(col, unit) → DuckDB DATE_TRUNC('unit', col)
    assert "DATE_TRUNC('DAY', d)" in out
    _assert_valid_duckdb(out)


def test_transpile_safe_cast_becomes_try_cast():
    out = transpile_bq_to_duckdb("SELECT SAFE_CAST(x AS INT64) FROM t")
    assert "TRY_CAST" in out.upper()
    _assert_valid_duckdb(out)


def test_transpile_safe_divide_becomes_case():
    out = transpile_bq_to_duckdb("SELECT SAFE_DIVIDE(a, b) FROM t")
    assert "safe_divide" not in out.lower()  # must be rewritten, not passed through
    assert "CASE" in out.upper()
    _assert_valid_duckdb(out)


def test_transpile_date_sub_interval():
    out = transpile_bq_to_duckdb("SELECT DATE_SUB(d, INTERVAL 1 DAY) FROM t")
    assert "INTERVAL" in out.upper()
    _assert_valid_duckdb(out)


def test_transpile_extract_and_format_and_parse_date():
    for sql in (
        "SELECT EXTRACT(YEAR FROM d) FROM t",
        "SELECT FORMAT_DATE('%Y-%m', d) FROM t",
        "SELECT PARSE_DATE('%Y-%m-%d', s) FROM t",
        "SELECT APPROX_QUANTILES(x, 100) FROM t",
    ):
        out = transpile_bq_to_duckdb(sql)
        _assert_valid_duckdb(out)


def test_transpile_full_widget_query():
    sql = """
    SELECT DATE_TRUNC(`order_date`, DAY) AS d,
           SAFE_DIVIDE(SUM(`revenue`), COUNT(*)) AS avg_rev
    FROM `csv_42`
    WHERE `order_date` >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY 1
    """
    out = transpile_bq_to_duckdb(sql)
    assert "`" not in out
    _assert_valid_duckdb(out)


def test_transpile_raises_on_parse_failure():
    with pytest.raises(UntranspilableSQLError):
        transpile_bq_to_duckdb("SELECT @@@ ;;; not valid sql")


def test_transpile_raises_on_unsupported_function():
    # ST_GEOGPOINT has no DuckDB-core equivalent — must fail loudly, not emit
    # SQL that errors at runtime.
    with pytest.raises(UntranspilableSQLError) as ei:
        transpile_bq_to_duckdb("SELECT ST_GEOGPOINT(lng, lat) FROM t")
    assert "st_geogpoint" in str(ei.value).lower()
