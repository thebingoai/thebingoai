import pytest

from backend.utils.sql_refs import extract_table_refs, rewrite_table_refs, can_parse


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
