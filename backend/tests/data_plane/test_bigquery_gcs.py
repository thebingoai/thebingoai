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
    mock_bq = MagicMock()
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
