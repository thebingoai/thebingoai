"""Tests for BigQueryGCSPlane (mocked — no real GCP calls)."""
import io
import pytest
import pyarrow as pa
from unittest.mock import MagicMock, patch, call


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


@pytest.fixture
def sample_table():
    return pa.table({"id": pa.array([1, 2], type=pa.int64()), "val": pa.array(["a", "b"])})


def test_write_parquet_uploads_to_gcs(plane, scope, sample_table):
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs = MagicMock()
    mock_gcs.bucket.return_value = mock_bucket

    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = []

    with patch.object(plane, "_gcs", return_value=mock_gcs), \
         patch.object(plane, "_bq", return_value=mock_bq):
        plane.write_parquet(scope, "sales", sample_table)

    assert mock_blob.upload_from_string.called
    args = mock_blob.upload_from_string.call_args
    data = args[0][0]
    # Verify it's valid Parquet
    import pyarrow.parquet as pq
    recovered = pq.read_table(io.BytesIO(data))
    assert recovered.num_rows == 2


def test_write_is_atomic_on_final_commit(plane, scope, sample_table):
    """GCS resumable upload only finalises on last chunk — upload_from_string is the commit."""
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs = MagicMock()
    mock_gcs.bucket.return_value = mock_bucket
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = []

    with patch.object(plane, "_gcs", return_value=mock_gcs), \
         patch.object(plane, "_bq", return_value=mock_bq):
        plane.write_parquet(scope, "t", sample_table)

    # upload_from_string is the atomic commit call
    assert mock_blob.upload_from_string.call_count == 1


def test_register_table_creates_external_bq_table(plane, scope, sample_table):
    """register_table is update-or-create; the create branch fires on NotFound."""
    from google.cloud.exceptions import NotFound
    mock_bq = MagicMock()
    mock_bq.update_table.side_effect = NotFound("table missing")

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane.register_table(scope, "sales", "gs://test-bucket/data_plane/org/org-1/sales/*", sample_table.schema)

    assert mock_bq.create_table.called


def test_query_rewrites_table_names(plane, scope):
    mock_bq = MagicMock()
    # BQ table name for OwnerScope("org","org-1") + "sales" → "org__org-1__sales"
    mock_bq.list_tables.return_value = [MagicMock(table_id="org__org-1__sales")]
    rows_iter = MagicMock()
    rows_iter.schema = []
    rows_iter.__iter__ = lambda s: iter([])
    mock_bq.query.return_value = MagicMock(result=lambda: rows_iter)

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane.query(scope, "SELECT * FROM sales")

    sql_arg = mock_bq.query.call_args[0][0]
    assert "test-proj.test_dataset." in sql_arg


def test_credentials_per_instance(plane):
    """GCS + BQ clients are configured per-instance from provided SA JSON."""
    plane2 = __import__("backend.data_plane.bigquery_gcs", fromlist=["BigQueryGCSPlane"]).BigQueryGCSPlane(
        gcp_project="other-proj",
        gcs_bucket="other-bucket",
        bq_dataset="other_ds",
        service_account_json='{"type":"service_account"}',
    )
    assert plane._project != plane2._project


# ── Native MERGE-on-ingest path (Option A) ─────────────────────────────────

def _mock_gcs():
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs = MagicMock()
    mock_gcs.bucket.return_value = mock_bucket
    return mock_gcs, mock_blob


def _insights_schema():
    """Schema mirroring Facebook insights_daily: keyed by (ad_id, date_start)."""
    return pa.schema([
        pa.field("ad_id", pa.string(), nullable=False),
        pa.field("date_start", pa.date32(), nullable=False),
        pa.field("spend", pa.float64()),
        pa.field("impressions", pa.int64()),
    ])


def _insights_table():
    return pa.table(
        {
            "ad_id": pa.array(["a1", "a2"], type=pa.string()),
            "date_start": pa.array([__import__("datetime").date(2026, 5, 17)] * 2, type=pa.date32()),
            "spend": pa.array([10.0, 20.0]),
            "impressions": pa.array([100, 200], type=pa.int64()),
        },
        schema=_insights_schema(),
    )


def test_resolve_partition_field_picks_date_start():
    from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
    assert BigQueryGCSPlane._resolve_partition_field(_insights_schema()) == "date_start"


def test_resolve_partition_field_returns_none_when_no_date_col():
    from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("name", pa.string()),
    ])
    assert BigQueryGCSPlane._resolve_partition_field(schema) is None


def test_resolve_cluster_fields_intersects_with_schema():
    from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
    schema = _insights_schema()
    assert BigQueryGCSPlane._resolve_cluster_fields(
        schema, ("ad_id", "date_start", "missing")
    ) == ["ad_id", "date_start"]


def test_resolve_cluster_fields_caps_at_four():
    from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
    schema = pa.schema([pa.field(f"k{i}", pa.string()) for i in range(6)])
    assert len(BigQueryGCSPlane._resolve_cluster_fields(
        schema, tuple(f"k{i}" for i in range(6))
    )) == 4


def test_native_merge_disabled_for_non_org_scope(plane):
    """User/team scopes never go through the MERGE path — flag bypass returns False."""
    from backend.data_plane.scope import OwnerScope
    assert plane._native_merge_enabled(OwnerScope("user", "u1")) is False
    assert plane._native_merge_enabled(OwnerScope("team", "t1")) is False


def test_native_merge_falls_back_when_flag_lookup_raises(plane, scope):
    """Flag lookup failure fails closed to legacy path (no Exception escapes)."""
    with patch("backend.config.feature_flags.enabled", side_effect=RuntimeError("redis down")):
        assert plane._native_merge_enabled(scope) is False


def test_write_parquet_with_unique_key_flag_off_uses_bronze_view(plane, scope):
    """Flag disabled → legacy _register_bronze_and_view path runs."""
    mock_gcs, _ = _mock_gcs()
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = []

    with patch.object(plane, "_gcs", return_value=mock_gcs), \
         patch.object(plane, "_bq", return_value=mock_bq), \
         patch("backend.config.feature_flags.enabled", return_value=False), \
         patch.object(plane, "_register_bronze_and_view") as legacy, \
         patch.object(plane, "_merge_into_native") as native:
        plane.write_parquet(scope, "insights_daily", _insights_table(),
                            unique_key=("ad_id", "date_start"))

    legacy.assert_called_once()
    native.assert_not_called()


def test_write_parquet_with_unique_key_flag_on_uses_native_merge(plane, scope):
    """Flag enabled → new _merge_into_native path runs."""
    mock_gcs, _ = _mock_gcs()
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = []

    with patch.object(plane, "_gcs", return_value=mock_gcs), \
         patch.object(plane, "_bq", return_value=mock_bq), \
         patch("backend.config.feature_flags.enabled", return_value=True), \
         patch.object(plane, "_register_bronze_and_view") as legacy, \
         patch.object(plane, "_merge_into_native") as native:
        plane.write_parquet(scope, "insights_daily", _insights_table(),
                            unique_key=("ad_id", "date_start"))

    native.assert_called_once()
    legacy.assert_not_called()
    # Verify the dt argument is today (UTC).
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert native.call_args.args[4] == today


def test_merge_into_native_creates_partitioned_clustered_table(plane, scope):
    """First run creates a native table with PARTITION BY date_start + CLUSTER BY unique_key."""
    from google.cloud.exceptions import NotFound
    mock_bq = MagicMock()
    # No prior table at user-facing name → NotFound on first get_table.
    mock_bq.get_table.side_effect = NotFound("not found")
    # update_table on stage external also NotFound → falls through to create.
    mock_bq.update_table.side_effect = NotFound("stage missing")

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane._merge_into_native(
            scope, "insights_daily",
            _insights_schema(), ("ad_id", "date_start"),
            dt="2026-05-17",
        )

    # First create_table call is the native table.
    create_calls = mock_bq.create_table.call_args_list
    assert len(create_calls) >= 1
    native_table = create_calls[0].args[0]
    assert native_table.time_partitioning is not None
    assert native_table.time_partitioning.field == "date_start"
    assert native_table.clustering_fields == ["ad_id", "date_start"]
    # exists_ok=True so subsequent runs are no-ops.
    assert create_calls[0].kwargs.get("exists_ok") is True


def test_merge_into_native_drops_legacy_view(plane, scope):
    """A pre-existing view at the user-facing name is dropped on first merge."""
    mock_bq = MagicMock()
    existing_view = MagicMock(table_type="VIEW")
    mock_bq.get_table.return_value = existing_view
    from google.cloud.exceptions import NotFound
    mock_bq.update_table.side_effect = NotFound("stage missing")

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane._merge_into_native(
            scope, "insights_daily",
            _insights_schema(), ("ad_id", "date_start"),
            dt="2026-05-17",
        )

    # delete_table called on the view's full id.
    assert mock_bq.delete_table.called
    deleted_id = mock_bq.delete_table.call_args.args[0]
    assert deleted_id.endswith("insights_daily")
    assert not deleted_id.endswith("_stage")
    assert not deleted_id.endswith("_bronze")


def test_merge_into_native_emits_merge_sql_with_correct_clauses(plane, scope):
    """MERGE SQL: ON on key cols, UPDATE on non-key cols, INSERT on all cols."""
    from google.cloud.exceptions import NotFound
    mock_bq = MagicMock()
    mock_bq.get_table.side_effect = NotFound("none")
    mock_bq.update_table.side_effect = NotFound("none")

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane._merge_into_native(
            scope, "insights_daily",
            _insights_schema(), ("ad_id", "date_start"),
            dt="2026-05-17",
        )

    # Last query call is the MERGE.
    merge_sql = mock_bq.query.call_args.args[0]
    assert "MERGE INTO" in merge_sql
    assert "T.`ad_id` = S.`ad_id`" in merge_sql
    assert "T.`date_start` = S.`date_start`" in merge_sql
    # UPDATE SET should target non-key cols only.
    assert "T.`spend` = S.`spend`" in merge_sql
    assert "T.`impressions` = S.`impressions`" in merge_sql
    # Key cols are not in UPDATE SET (they're equal by the ON clause).
    update_section = merge_sql.split("WHEN MATCHED")[1].split("WHEN NOT MATCHED")[0]
    assert "T.`ad_id` = S.`ad_id`" not in update_section
    # INSERT contains all columns.
    assert "INSERT (`ad_id`, `date_start`, `spend`, `impressions`)" in merge_sql


def test_merge_into_native_omits_when_matched_for_key_only_schema(plane, scope):
    """Schema with no non-key columns → only WHEN NOT MATCHED clause."""
    from google.cloud.exceptions import NotFound
    mock_bq = MagicMock()
    mock_bq.get_table.side_effect = NotFound("none")
    mock_bq.update_table.side_effect = NotFound("none")

    key_only_schema = pa.schema([
        pa.field("id", pa.string(), nullable=False),
    ])

    with patch.object(plane, "_bq", return_value=mock_bq):
        plane._merge_into_native(
            scope, "ad_account", key_only_schema, ("id",), dt="2026-05-17",
        )

    merge_sql = mock_bq.query.call_args.args[0]
    assert "WHEN MATCHED" not in merge_sql
    assert "WHEN NOT MATCHED" in merge_sql


def test_list_tables_hides_stage_and_bronze(plane):
    """list_tables filters internal staging + audit tables."""
    from backend.data_plane.scope import OwnerScope
    s = OwnerScope("org", "org-1")
    mock_bq = MagicMock()
    mock_bq.list_tables.return_value = [
        MagicMock(table_id="org__org-1__campaigns"),
        MagicMock(table_id="org__org-1__campaigns_stage"),
        MagicMock(table_id="org__org-1__campaigns_bronze"),
        MagicMock(table_id="org__org-1__insights_daily"),
    ]

    with patch.object(plane, "_bq", return_value=mock_bq):
        names = plane.list_tables(s)

    assert "campaigns" in names
    assert "insights_daily" in names
    assert "campaigns_stage" not in names
    assert "campaigns_bronze" not in names
