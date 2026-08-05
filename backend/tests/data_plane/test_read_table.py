"""Reading a known table must not discover the namespace first.

`services.dashboard_cache.read_widget_data_plane` knows the exact `_dash_*`
table name, but it went through `table_exists` + `query`. On BigQuery that is
two live metadata round-trips before the query job starts: a `get_table`, then
a fully paginated `tables.list` inside `_rewrite_sql` — uncached, and scaling
with dataset size. At ~200-600ms each across a 20-widget dashboard that is
seconds of open latency, all of it with the request's PG pool slot checked out.
This is the live prod serving path today (`duckdb_widget_serving` is off).
"""

from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest


@pytest.fixture
def plane():
    from backend.data_plane.bigquery_gcs import BigQueryGCSPlane

    return BigQueryGCSPlane(
        gcp_project="test-proj",
        gcs_bucket="test-bucket",
        bq_dataset="test_dataset",
        service_account_json='{"type":"service_account"}',
    )


@pytest.fixture
def scope():
    from backend.data_plane.scope import OwnerScope

    return OwnerScope("org", "org-1")


def _bq_returning_rows():
    """A mock BQ client whose query() yields one row of (id, val)."""
    row = MagicMock()
    row.values.return_value = (1, "a")
    rows_iter = MagicMock()
    rows_iter.schema = [MagicMock(name="f1"), MagicMock(name="f2")]
    rows_iter.schema[0].name = "id"
    rows_iter.schema[1].name = "val"
    rows_iter.__iter__ = lambda _self: iter([row])

    job = MagicMock()
    job.result.return_value = rows_iter

    client = MagicMock()
    client.query.return_value = job
    return client


# ---------------------------------------------------------------------------
# BigQuery: zero metadata round-trips
# ---------------------------------------------------------------------------


def test_read_table_makes_no_metadata_calls(plane, scope):
    """The whole point: no tables.list, no get_table."""
    mock_bq = _bq_returning_rows()

    with patch.object(plane, "_bq", return_value=mock_bq):
        result = plane.read_table(scope, "_dash_1__w1")

    assert mock_bq.list_tables.call_count == 0, (
        "listing the dataset to resolve a name we already know is the bug"
    )
    assert mock_bq.get_table.call_count == 0, (
        "the query job is the existence check; a get_table probe is redundant"
    )
    assert result.columns == ["id", "val"]
    assert result.rows == [(1, "a")]


def test_read_table_fully_qualifies_the_known_name(plane, scope):
    mock_bq = _bq_returning_rows()

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane.read_table(scope, "_dash_1__w1")

    sql = mock_bq.query.call_args[0][0]
    assert sql == "SELECT * FROM `test-proj.test_dataset.org__org-1___dash_1__w1`", (
        f"unexpected SQL: {sql}"
    )


def test_read_table_returns_none_for_a_missing_table(plane, scope):
    from google.cloud.exceptions import NotFound

    mock_bq = MagicMock()
    mock_bq.query.side_effect = NotFound("Not found: Table x")

    with patch.object(plane, "_bq", return_value=mock_bq):
        assert plane.read_table(scope, "_dash_1__gone") is None


def test_query_still_rewrites_bare_names(plane, scope):
    """read_table must not have cost `query` its identifier resolution."""
    mock_bq = _bq_returning_rows()
    mock_bq.list_tables.return_value = [MagicMock(table_id="org__org-1__sales")]

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane.query(scope, "SELECT * FROM sales")

    sql = mock_bq.query.call_args[0][0]
    assert "`test-proj.test_dataset.org__org-1__sales`" in sql


# ---------------------------------------------------------------------------
# list_tables memoization
# ---------------------------------------------------------------------------


def test_list_tables_is_memoized_within_the_ttl(plane, scope):
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = [MagicMock(table_id="org__org-1__sales")]

    with patch.object(plane, "_bq", return_value=mock_bq):
        first = plane.list_tables(scope)
        second = plane.list_tables(scope)

    assert first == second == ["sales"]
    assert mock_bq.list_tables.call_count == 1, (
        "the dataset listing is a paginated API call; it must not repeat per query"
    )


def test_the_memo_is_per_scope(plane):
    """One tenant's listing must never be served to another."""
    from backend.data_plane.scope import OwnerScope

    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = [
        MagicMock(table_id="org__org-1__sales"),
        MagicMock(table_id="org__org-2__payroll"),
    ]

    with patch.object(plane, "_bq", return_value=mock_bq):
        one = plane.list_tables(OwnerScope("org", "org-1"))
        two = plane.list_tables(OwnerScope("org", "org-2"))

    assert one == ["sales"]
    assert two == ["payroll"]


def test_the_memo_expires(plane, scope, monkeypatch):
    import backend.data_plane.bigquery_gcs as mod

    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = [MagicMock(table_id="org__org-1__sales")]

    monkeypatch.setattr(mod, "_LIST_TABLES_TTL_S", -1.0)  # already expired

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane.list_tables(scope)
        plane.list_tables(scope)

    assert mock_bq.list_tables.call_count == 2, (
        "a permanent cache would hide tables created by the Celery workers"
    )


def test_registering_a_table_invalidates_the_memo(plane, scope):
    """Otherwise a table created in this process stays unqualifiable by
    _rewrite_sql until the TTL lapses, and the next query against it fails."""
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = []

    with patch.object(plane, "_bq", return_value=mock_bq):
        assert plane.list_tables(scope) == []

        mock_bq.list_tables.return_value = [MagicMock(table_id="org__org-1__fresh")]
        plane.register_table(
            scope, "fresh", "gs://test-bucket/p/*", pa.schema([pa.field("id", pa.int64())])
        )

        assert plane.list_tables(scope) == ["fresh"]


def test_the_memo_returns_a_copy(plane, scope):
    """A caller mutating the returned list must not corrupt the cache."""
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = [MagicMock(table_id="org__org-1__sales")]

    with patch.object(plane, "_bq", return_value=mock_bq):
        first = plane.list_tables(scope)
        first.append("injected")
        assert plane.list_tables(scope) == ["sales"]


# ---------------------------------------------------------------------------
# The local plane keeps the same contract
# ---------------------------------------------------------------------------


def test_local_read_table_round_trips(tmp_path):
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
    from backend.data_plane.scope import OwnerScope

    local = LocalFilesystemDataPlane(root_path=str(tmp_path))
    # User scope, matching test_local_filesystem.py: an org scope makes the
    # governance plugin's query-audit middleware write an audit_events row, which
    # FK-fails against an organizations table this test never seeds.
    s = OwnerScope("user", "test-user")
    local.write_parquet(s, "sales", pa.table({"id": pa.array([1, 2], type=pa.int64())}))

    result = local.read_table(s, "sales")

    assert result is not None
    # `dt` is the Hive partition column; the local plane surfaces it through
    # SELECT *, exactly as plane.query() already did here.
    assert result.columns == ["id", "dt"]
    assert result.row_count == 2


def test_local_read_table_returns_none_when_absent(tmp_path):
    from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
    from backend.data_plane.scope import OwnerScope

    local = LocalFilesystemDataPlane(root_path=str(tmp_path))

    assert local.read_table(OwnerScope("user", "test-user"), "nope") is None
