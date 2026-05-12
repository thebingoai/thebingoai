"""BigQueryGCSPlane — Parquet on GCS + BigQuery as the query engine.

Atomic writes via google-cloud-storage resumable upload: the object becomes
visible to readers only after the final commit chunk lands (P1.1).
"""
from __future__ import annotations

import io
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from backend.connectors.base import QueryResult, TableSchema
from .scope import OwnerScope

logger = logging.getLogger(__name__)


class BigQueryGCSPlane:
    """DataPlane backed by GCS storage + BigQuery query engine.

    config keys (from data_planes.config JSONB):
        gcp_project   – GCP project ID
        gcs_bucket    – GCS bucket name (without gs:// prefix)
        bq_dataset    – BigQuery dataset ID for external tables

    credentials_encrypted is the Fernet-encrypted service-account JSON string,
    decrypted before being passed to this constructor.
    """

    def __init__(
        self,
        gcp_project: str,
        gcs_bucket: str,
        bq_dataset: str,
        service_account_json: str,
    ) -> None:
        self._project = gcp_project
        self._bucket_name = gcs_bucket
        self._dataset = bq_dataset
        self._sa_json = service_account_json
        self._bq_client = None
        self._gcs_client = None

    # ── Lazy client accessors ─────────────────────────────────────────────

    def _bq(self):
        if self._bq_client is None:
            from backend.auth.gcp import bigquery_client_from_json
            self._bq_client = bigquery_client_from_json(self._sa_json, self._project)
        return self._bq_client

    def _gcs(self):
        if self._gcs_client is None:
            from backend.auth.gcp import gcs_client_from_json
            self._gcs_client = gcs_client_from_json(self._sa_json)
        return self._gcs_client

    def close(self) -> None:
        if self._bq_client:
            try:
                self._bq_client.close()
            except Exception:
                pass
            self._bq_client = None

    # ── GCS path helpers ──────────────────────────────────────────────────

    def _gcs_prefix(self, scope: OwnerScope, table: str, dt: str) -> str:
        return f"data_plane/{scope.as_path()}/{table}/dt={dt}"

    def _gcs_object_path(self, scope: OwnerScope, table: str, dt: str, part: int = 0) -> str:
        return f"{self._gcs_prefix(scope, table, dt)}/part-{part}.parquet"

    # ── DataPlane interface ───────────────────────────────────────────────

    def write_parquet(
        self,
        scope: OwnerScope,
        table: str,
        data: pa.Table | Iterator[pa.RecordBatch],
        mode: str = "overwrite",
    ) -> None:
        dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        gcs_path = self._gcs_object_path(scope, table, dt)

        if isinstance(data, pa.Table):
            arrow_table = data
        else:
            batches = list(data)
            arrow_table = pa.Table.from_batches(batches) if batches else pa.table({})

        buf = io.BytesIO()
        pq.write_table(arrow_table, buf)
        parquet_bytes = buf.getvalue()

        bucket = self._gcs().bucket(self._bucket_name)
        blob = bucket.blob(gcs_path)
        # Resumable upload — atomic on final commit (P1.1)
        blob.upload_from_string(parquet_bytes, content_type="application/octet-stream")

        logger.debug("Wrote GCS parquet %s → gs://%s/%s", table, self._bucket_name, gcs_path)

        # Register the BQ external table after write
        self.register_table(scope, table, f"gs://{self._bucket_name}/{self._gcs_prefix(scope, table, '*')}", arrow_table.schema)

    def register_table(
        self,
        scope: OwnerScope,
        table: str,
        path: str,
        schema: pa.Schema,
    ) -> None:
        from google.cloud import bigquery

        bq_table_name = self._bq_table_name(scope, table)
        full_table_id = f"{self._project}.{self._dataset}.{bq_table_name}"

        bq_schema = _arrow_schema_to_bq(schema)
        external_config = bigquery.ExternalConfig("PARQUET")
        external_config.source_uris = [path if path.endswith("*") else path + "/*"]
        external_config.hive_partitioning = bigquery.HivePartitioningOptions()
        external_config.hive_partitioning.mode = "AUTO"
        external_config.hive_partitioning.source_uri_prefix = path.rstrip("*").rstrip("/")

        table_ref = bigquery.Table(full_table_id, schema=bq_schema)
        table_ref.external_data_configuration = external_config

        # Update-or-create. We previously delete+create'd to refresh the
        # external config but that requires `bigquery.tables.delete`, which we
        # do not want Bingo to call against customer data. `update_table` only
        # needs `bigquery.tables.update`.
        from google.cloud.exceptions import NotFound
        try:
            self._bq().update_table(
                table_ref,
                fields=["schema", "external_data_configuration"],
            )
        except NotFound:
            self._bq().create_table(table_ref)
        logger.debug("Registered BQ external table %s", full_table_id)

    def query(
        self,
        scope: OwnerScope,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        # Rewrite bare table names to fully-qualified BQ names
        rewritten_sql = self._rewrite_sql(scope, sql)
        start = time.time()
        job = self._bq().query(rewritten_sql)
        rows_iter = job.result()
        columns = [f.name for f in rows_iter.schema]
        rows = [tuple(row.values()) for row in rows_iter]
        execution_time_ms = (time.time() - start) * 1000
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=execution_time_ms,
        )

    def list_tables(self, scope: OwnerScope, namespace: str | None = None) -> list[str]:
        prefix = self._scope_bq_prefix(scope)
        tables = []
        for t in self._bq().list_tables(self._dataset):
            if t.table_id.startswith(prefix):
                # Strip the scope prefix to return bare table names
                bare = t.table_id[len(prefix):]
                tables.append(bare)
        return tables

    def drop_table(self, scope: OwnerScope, table: str) -> None:
        # Intentional no-op: Bingo's no-delete policy means the cloud plane
        # never destroys customer data. Pipeline / dbt-model delete cascades
        # remove the Bingo metadata row but leave the BQ table + GCS parquet
        # files in place; operators clean those up GCP-side if desired.
        full_table_id = (
            f"{self._project}.{self._dataset}.{self._bq_table_name(scope, table)}"
        )
        logger.info(
            "BigQueryGCSPlane.drop_table no-op for %s (Bingo never deletes customer data; "
            "remove the table + GCS prefix in your GCP project to reclaim storage).",
            full_table_id,
        )

    def table_exists(self, scope: OwnerScope, table: str) -> bool:
        from google.cloud.exceptions import NotFound
        full_table_id = f"{self._project}.{self._dataset}.{self._bq_table_name(scope, table)}"
        try:
            self._bq().get_table(full_table_id)
            return True
        except NotFound:
            return False

    def to_dbt_profile(self) -> dict:
        import json
        return {
            "type": "bigquery",
            "method": "service-account-json",
            "project": self._project,
            "dataset": self._dataset,
            "keyfile_json": json.loads(self._sa_json),
            "timeout_seconds": 300,
            "threads": 4,
        }

    def get_schema(self, scope: OwnerScope, table: str) -> pa.Schema:
        from google.cloud.exceptions import NotFound
        full_table_id = f"{self._project}.{self._dataset}.{self._bq_table_name(scope, table)}"
        try:
            bq_table = self._bq().get_table(full_table_id)
        except NotFound:
            raise FileNotFoundError(f"Table {table!r} not found in scope {scope}")
        return _bq_schema_to_arrow(bq_table.schema)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _scope_bq_prefix(self, scope: OwnerScope) -> str:
        return scope.as_path().replace("/", "__") + "__"

    def _bq_table_name(self, scope: OwnerScope, table: str) -> str:
        safe_scope = scope.as_path().replace("/", "__")
        safe_table = table.replace("-", "_")
        return f"{safe_scope}__{safe_table}"

    def _rewrite_sql(self, scope: OwnerScope, sql: str) -> str:
        """Replace bare table names with fully-qualified BQ references."""
        import re
        prefix = f"{self._project}.{self._dataset}."
        tables = self.list_tables(scope)
        result = sql
        for t in sorted(tables, key=len, reverse=True):  # longest first
            bq_name = self._bq_table_name(scope, t)
            # Backtick the fully-qualified id: scope/dataset can contain hyphens
            # (UUID-based org ids, customer dataset names), which BQ requires
            # to be quoted in SQL identifiers.
            result = re.sub(
                rf"\b{re.escape(t)}\b",
                f"`{prefix}{bq_name}`",
                result,
            )
        return result


# ---------------------------------------------------------------------------
# Arrow ↔ BigQuery schema conversion helpers
# ---------------------------------------------------------------------------

def _arrow_schema_to_bq(schema: pa.Schema) -> list:
    from google.cloud.bigquery import SchemaField
    _type_map = {
        pa.int8(): "INT64", pa.int16(): "INT64", pa.int32(): "INT64", pa.int64(): "INT64",
        pa.float32(): "FLOAT64", pa.float64(): "FLOAT64",
        pa.bool_(): "BOOL",
        pa.string(): "STRING", pa.large_string(): "STRING",
        pa.date32(): "DATE", pa.date64(): "DATE",
    }
    fields = []
    for field in schema:
        bq_type = _type_map.get(field.type, "STRING")
        mode = "NULLABLE" if field.nullable else "REQUIRED"
        fields.append(SchemaField(field.name, bq_type, mode=mode))
    return fields


def _bq_schema_to_arrow(bq_schema) -> pa.Schema:
    _type_map = {
        "INT64": pa.int64(), "INTEGER": pa.int64(),
        "FLOAT64": pa.float64(), "FLOAT": pa.float64(),
        "BOOL": pa.bool_(), "BOOLEAN": pa.bool_(),
        "STRING": pa.string(),
        "DATE": pa.date32(),
        "TIMESTAMP": pa.timestamp("us"),
        "BYTES": pa.binary(),
    }
    fields = []
    for f in bq_schema:
        arrow_type = _type_map.get(f.field_type, pa.string())
        nullable = f.mode != "REQUIRED"
        fields.append(pa.field(f.name, arrow_type, nullable=nullable))
    return pa.schema(fields)
