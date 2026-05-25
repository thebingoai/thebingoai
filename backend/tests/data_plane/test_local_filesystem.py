"""Tests for LocalFilesystemDataPlane."""
import os
import threading
import pytest
import pyarrow as pa

from backend.data_plane.scope import OwnerScope
from backend.data_plane.local_filesystem import LocalFilesystemDataPlane


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


@pytest.fixture
def plane(root):
    p = LocalFilesystemDataPlane(root_path=root)
    yield p
    p.close()


@pytest.fixture
def scope():
    return OwnerScope("user", "test-user")


@pytest.fixture
def scope_b():
    return OwnerScope("user", "other-user")


@pytest.fixture
def sample_table():
    return pa.table({
        "id": pa.array([1, 2, 3], type=pa.int64()),
        "name": pa.array(["Alice", "Bob", "Carol"], type=pa.string()),
        "score": pa.array([1.1, 2.2, 3.3], type=pa.float64()),
    })


def test_write_and_table_exists(plane, scope, sample_table):
    plane.write_parquet(scope, "test", sample_table)
    assert plane.table_exists(scope, "test") is True


def test_table_not_exists_before_write(plane, scope):
    assert plane.table_exists(scope, "no_such_table") is False


def test_query_count(plane, scope, sample_table):
    plane.write_parquet(scope, "test", sample_table)
    result = plane.query(scope, "SELECT count(*) AS n FROM test")
    assert result.rows[0][0] == 3


def test_query_named_param_binding(plane, scope, sample_table):
    # DuckDB `$name` placeholders bind from the dict by name (duckdb-dialect
    # inject_filters output).
    plane.write_parquet(scope, "test", sample_table)
    result = plane.query(scope, "SELECT name FROM test WHERE id = $_f0", {"_f0": 2})
    assert [r[0] for r in result.rows] == ["Bob"]


def test_query_positional_param_binding_preserved(plane, scope, sample_table):
    # Legacy positional `?` placeholder path still binds values in order.
    plane.write_parquet(scope, "test", sample_table)
    result = plane.query(scope, "SELECT name FROM test WHERE id = ?", {"x": 3})
    assert [r[0] for r in result.rows] == ["Carol"]


def test_query_truncates_at_max_rows(plane, scope, monkeypatch):
    import backend.config as cfg
    monkeypatch.setattr(cfg.settings, "max_query_rows", 5, raising=False)
    big = pa.table({"i": pa.array(list(range(20)), type=pa.int64())})
    plane.write_parquet(scope, "big", big)
    result = plane.query(scope, "SELECT i FROM big ORDER BY i")
    assert result.truncated is True
    assert result.row_count == 5


def test_atomic_write_tmp_cleaned_on_failure(plane, scope, root):
    """Simulate failure during write — .tmp file must not remain."""
    bad_data = iter([pa.record_batch({"x": pa.array([1])}, schema=pa.schema([("x", pa.int64())]))])

    # Monkey-patch rename to fail
    original_rename = os.rename
    def failing_rename(src, dst):
        raise OSError("Simulated rename failure")

    import backend.data_plane.local_filesystem as _mod
    original = _mod.os.rename
    _mod.os.rename = failing_rename
    try:
        with pytest.raises(OSError):
            plane.write_parquet(scope, "atomic_test", bad_data)
    finally:
        _mod.os.rename = original

    # .tmp file should have been cleaned up
    scope_root = plane._scope_root(scope)
    tmp_files = []
    for dirpath, _, files in os.walk(scope_root):
        tmp_files.extend(f for f in files if f.endswith(".tmp"))
    assert tmp_files == [], f"Leftover .tmp files: {tmp_files}"


def test_cross_scope_isolation(plane, scope, scope_b, sample_table):
    plane.write_parquet(scope, "test", sample_table)
    assert plane.table_exists(scope, "test") is True
    assert plane.table_exists(scope_b, "test") is False


def test_list_tables(plane, scope, sample_table):
    plane.write_parquet(scope, "table_a", sample_table)
    plane.write_parquet(scope, "table_b", sample_table)
    tables = plane.list_tables(scope)
    assert set(tables) >= {"table_a", "table_b"}


def test_drop_table(plane, scope, sample_table):
    plane.write_parquet(scope, "to_drop", sample_table)
    assert plane.table_exists(scope, "to_drop") is True
    plane.drop_table(scope, "to_drop")
    assert plane.table_exists(scope, "to_drop") is False


def test_schema_round_trip(plane, scope):
    from datetime import datetime
    t = pa.table({
        "i": pa.array([1, 2], type=pa.int64()),
        "s": pa.array(["a", None], type=pa.string()),
        "ts": pa.array([datetime(2024, 1, 1), datetime(2024, 1, 2)], type=pa.timestamp("us")),
    })
    plane.write_parquet(scope, "typed", t)
    # Hive-partitioned read includes the dt partition key — exclude it in assertion
    result = plane.query(scope, "SELECT i, s, ts FROM typed ORDER BY i")
    assert result.columns == ["i", "s", "ts"]
    assert result.rows[0][0] == 1
    assert result.rows[1][1] is None  # nullable preserved


def test_overwrite_replaces_data(plane, scope):
    t1 = pa.table({"v": pa.array([1, 2, 3], type=pa.int64())})
    t2 = pa.table({"v": pa.array([99], type=pa.int64())})
    plane.write_parquet(scope, "overwrite_test", t1)
    plane.write_parquet(scope, "overwrite_test", t2, mode="overwrite")
    result = plane.query(scope, "SELECT count(*) AS n FROM overwrite_test")
    assert result.rows[0][0] == 1


def test_connection_per_task(root, scope, sample_table):
    """10 threads each open + close their own LocalFilesystemDataPlane without error."""
    errors = []

    def worker(_i):
        p = LocalFilesystemDataPlane(root_path=root)
        try:
            p.write_parquet(scope, f"task_{_i}", sample_table)
            p.query(scope, f"SELECT count(*) FROM task_{_i}")
        except Exception as e:
            errors.append(e)
        finally:
            p.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
