"""BigQueryGCSPlane — Parquet on GCS + BigQuery as the query engine.

Atomic writes via google-cloud-storage resumable upload: the object becomes
visible to readers only after the final commit chunk lands (P1.1).
"""
from __future__ import annotations

import io
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from backend.connectors.base import QueryResult, TableSchema
from .scope import OwnerScope

logger = logging.getLogger(__name__)

# How long a `list_tables` result is reused per scope. Short on purpose: the
# listing feeds `_rewrite_sql`, so a stale entry means a table created by
# another process (a pipeline run on a Celery worker) fails to be qualified
# until it expires. Same-process creation invalidates eagerly.
_LIST_TABLES_TTL_S = 30.0

_PYFORMAT_RE = re.compile(r'%\((\w+)\)s')
_ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_ISO_DATETIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')


def gcs_parquet_glob(bucket: str, scope: "OwnerScope", table: str) -> str:
    """gs:// glob over all `dt=` partitions of *table* for *scope*.

    Single source of truth for the lake path scheme (matches the prefix written
    by `BigQueryGCSPlane._gcs_prefix`); consumed by the Phase 2 DuckDB-over-GCS
    reader (`gcs_duckdb.GCSDuckDBReader`).
    """
    return f"gs://{bucket}/data_plane/{scope.as_path()}/{table}/dt=*/*.parquet"


def _pyformat_to_bq(query: str, params: dict[str, Any] | None):
    """Rewrite pyformat ``%(key)s`` placeholders to BigQuery ``@key`` syntax
    and build a list of ``ScalarQueryParameter`` for ``QueryJobConfig``.

    Returns ``(rewritten_sql, bq_params_list)``. No-op when ``params`` is empty.
    String values matching ``YYYY-MM-DD`` are bound as DATE so they compare
    cleanly against DATE columns; ISO datetime strings are bound as TIMESTAMP.
    """
    from google.cloud import bigquery

    if not params:
        return query, []

    used: set[str] = set()

    def _sub(match: "re.Match[str]") -> str:
        used.add(match.group(1))
        return f"@{match.group(1)}"

    converted = _PYFORMAT_RE.sub(_sub, query)

    def _bq_type(value: Any) -> str:
        if isinstance(value, bool):
            return "BOOL"
        if isinstance(value, int):
            return "INT64"
        if isinstance(value, float):
            return "FLOAT64"
        if isinstance(value, str):
            if _ISO_DATE_RE.match(value):
                return "DATE"
            if _ISO_DATETIME_RE.match(value):
                return "TIMESTAMP"
        return "STRING"

    bq_params = [
        bigquery.ScalarQueryParameter(k, _bq_type(params[k]), params[k])
        for k in used
    ]
    return converted, bq_params


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
        # Per-instance cache of (scope_kind, scope_id, table, register_kind)
        # keys that have already been registered. Skips redundant BQ metadata
        # calls when dlt drives many write_parquet batches into the same target.
        self._registered: set[tuple[str, str, str, str]] = set()
        # Per-scope `list_tables` memo: {scope_path: (expires_at, tables)}.
        # The listing is a fully paginated tables.list and was uncached, so
        # every _rewrite_sql paid for it. The plane instance is long-lived
        # (services.data_plane_service._bq_plane_cache), hence the TTL: a table
        # materialised by a pipeline must become visible without a redeploy.
        self._tables_memo: dict[str, tuple[float, list[str]]] = {}

    @property
    def bucket(self) -> str:
        """GCS bucket name (without gs:// prefix) — used by the DuckDB-over-GCS reader."""
        return self._bucket_name

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

    def _gcs_object_path(self, scope: OwnerScope, table: str, dt: str, part: str | int = 0) -> str:
        return f"{self._gcs_prefix(scope, table, dt)}/part-{part}.parquet"

    def storage_bytes(self, scope: OwnerScope) -> int:
        prefix = f"data_plane/{scope.as_path()}/"
        try:
            blobs = self._gcs().list_blobs(self._bucket_name, prefix=prefix)
            return sum(b.size or 0 for b in blobs)
        except Exception:
            logger.warning("storage_bytes scan failed for %s", scope, exc_info=True)
            return 0

    # ── DataPlane interface ───────────────────────────────────────────────

    def write_parquet(
        self,
        scope: OwnerScope,
        table: str,
        data: pa.Table | Iterator[pa.RecordBatch],
        mode: str = "overwrite",
        unique_key: tuple[str, ...] | None = None,
    ) -> None:
        import uuid
        dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Unique part suffix per call so multi-batch dlt loads accumulate in the
        # `dt=<date>/` partition instead of every batch overwriting `part-0`.
        part_id = uuid.uuid4().hex[:12] if mode != "overwrite" else "0"
        gcs_path = self._gcs_object_path(scope, table, dt, part=part_id)

        if isinstance(data, pa.Table):
            arrow_table = data
        else:
            batches = list(data)
            arrow_table = pa.Table.from_batches(batches) if batches else pa.table({})

        arrow_table = _downcast_ns_timestamps(arrow_table)
        arrow_table, renamed = bq_safe_column_names(arrow_table)
        if renamed and unique_key:
            # The key names the dedup view / MERGE join builds from — it has to
            # follow the Parquet rename or both fail after the object is written.
            unique_key = tuple(renamed.get(k, k) for k in unique_key)

        buf = io.BytesIO()
        pq.write_table(arrow_table, buf)
        parquet_bytes = buf.getvalue()

        bucket = self._gcs().bucket(self._bucket_name)
        blob = bucket.blob(gcs_path)
        # Resumable upload — atomic on final commit (P1.1)
        blob.upload_from_string(parquet_bytes, content_type="application/octet-stream")

        logger.debug("Wrote GCS parquet %s → gs://%s/%s", table, self._bucket_name, gcs_path)

        # Register the BQ surface. Cases:
        # 1a. `unique_key` declared + org-scoped + `native_merge_data_plane`
        #     flag on → native partitioned + clustered BQ table, populated via
        #     MERGE-on-ingest. Dedup once per pipeline run; widgets read a
        #     native table with stats + pruning, no per-query ROW_NUMBER.
        # 1b. `unique_key` declared, flag off (or non-org scope) → legacy
        #     bronze external (union of all `dt=*`) + silver dedup view.
        # 2.  `mode='overwrite'` with no key → single latest `dt=` partition
        #     (snapshot pin; history capped at the source's lookback window).
        # 3.  `mode='append'` → `dt=*/*` glob, no dedup, Hive `dt` queryable.
        # Old partitions remain on GCS for audit/replay regardless.
        # BigQuery external tables accept exactly one wildcard per source URI.
        # `*` matches across `/` boundaries, so a single trailing `*` after the
        # table prefix reads every Parquet across every `dt=` partition.
        table_prefix = f"data_plane/{scope.as_path()}/{table}/"
        if unique_key:
            if self._native_merge_enabled(scope):
                # MERGE must run every batch (each staging dt= partition needs
                # upsert into native). Skip the cache.
                self._merge_into_native(
                    scope, table, arrow_table.schema, unique_key, dt,
                )
            else:
                cache_key = (scope.kind, scope.id, table, "bronze_view")
                if cache_key not in self._registered:
                    bronze_uri = f"gs://{self._bucket_name}/{table_prefix}*"
                    bronze_prefix = f"gs://{self._bucket_name}/{table_prefix}"
                    self._register_bronze_and_view(
                        scope, table, bronze_uri, bronze_prefix,
                        arrow_table.schema, unique_key,
                    )
                    self._registered.add(cache_key)
        elif mode == "overwrite":
            # Overwrite uses a dt-pinned URI; register every batch because the
            # `dt=<today>` in the URI may differ from prior calls if the run
            # spans midnight. Skip the cache.
            uri = f"gs://{self._bucket_name}/{self._gcs_prefix(scope, table, dt)}/*"
            self.register_table(scope, table, uri, arrow_table.schema)
        else:
            cache_key = (scope.kind, scope.id, table, "plain_external")
            if cache_key not in self._registered:
                uri = f"gs://{self._bucket_name}/{table_prefix}*"
                self.register_table(scope, table, uri, arrow_table.schema)
                self._registered.add(cache_key)

    def _native_merge_enabled(self, scope: OwnerScope) -> bool:
        """Org-scoped feature gate for the MERGE-into-native path.

        Returns False for user/team scopes (no org_id to resolve flag against)
        and on any flag-lookup error (fail-closed to legacy bronze+view).
        """
        if scope.kind != "org":
            return False
        try:
            from backend.config.feature_flags import enabled
            return enabled(scope.id, "native_merge_data_plane")
        except Exception:
            logger.warning(
                "native_merge_data_plane flag lookup failed for %s; "
                "falling back to legacy bronze+view path", scope, exc_info=True,
            )
            return False

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

        # Hive partitioning is meaningful only when the URI globs over
        # multiple `dt=` partitions (true-delta pipelines, append mode).
        # Snapshot pipelines anchor at one `dt=YYYY-MM-DD/` dir — `dt` is
        # constant there, so omit Hive options to keep schema clean.
        # Detection: snapshot URIs contain `/dt=<date>/`; append URIs have
        # only a trailing `*` at the table root.
        import re
        if not re.search(r"/dt=[^/*]+/", path):
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
        self._invalidate_tables_memo(scope)
        logger.debug("Registered BQ external table %s", full_table_id)

    def put_raw_object(
        self,
        scope: OwnerScope,
        rel_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Store opaque bytes at *rel_path* in the per-Org bucket (non-Parquet sidecar)."""
        blob = self._gcs().bucket(self._bucket_name).blob(rel_path)
        blob.upload_from_string(data, content_type=content_type)
        logger.debug("Wrote raw object gs://%s/%s", self._bucket_name, rel_path)

    def get_raw_object(self, scope: OwnerScope, rel_path: str) -> bytes | None:
        """Read opaque bytes at *rel_path*; None when the object is absent."""
        from google.cloud.exceptions import NotFound
        blob = self._gcs().bucket(self._bucket_name).blob(rel_path)
        try:
            return blob.download_as_bytes()
        except NotFound:
            return None

    def delete_raw_object(self, scope: OwnerScope, rel_path: str) -> None:
        """Delete the raw object at *rel_path*; silently no-op when absent."""
        from google.cloud.exceptions import NotFound
        blob = self._gcs().bucket(self._bucket_name).blob(rel_path)
        try:
            blob.delete()
        except NotFound:
            pass

    def raw_object_exists(self, scope: OwnerScope, rel_path: str) -> bool:
        """Return True when a raw object exists at *rel_path*."""
        return self._gcs().bucket(self._bucket_name).blob(rel_path).exists()

    def query(
        self,
        scope: OwnerScope,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        return self._run_sql(self._rewrite_sql(scope, sql), params)

    def read_table(self, scope: OwnerScope, table: str) -> QueryResult | None:
        """Read one known table with zero metadata round-trips.

        The widget serving path (`services.dashboard_cache.read_widget_data_plane`)
        knows the exact `_dash_*` table name, yet going through `query()` cost two
        live BigQuery metadata calls before the job even started: `table_exists`
        does a `get_table`, and `_rewrite_sql` does a fully paginated
        `tables.list` of the dataset — uncached, and scaling with dataset size.
        At ~200-600ms each that is seconds of added dashboard-open latency per
        widget, every one of them with the request's PG pool slot checked out.

        The name is already fully determined by `_bq_table_name`, so qualify it
        and let the query job itself be the existence check.
        """
        from google.cloud.exceptions import NotFound

        full_table_id = f"{self._project}.{self._dataset}.{self._bq_table_name(scope, table)}"
        try:
            return self._run_sql(f"SELECT * FROM `{full_table_id}`")
        except NotFound:
            return None

    def _run_sql(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Execute already-qualified SQL. Callers own identifier resolution."""
        from google.cloud import bigquery

        bound_sql, bq_params = _pyformat_to_bq(sql, params)
        job_config = bigquery.QueryJobConfig(query_parameters=bq_params or [])
        # Default dataset so a *bare* table reference resolves to this plane's
        # dataset. `_rewrite_sql` only fully-qualifies tables it knows from
        # `list_tables` (scope-prefixed + `_dash_*`); a GA4 pipeline target like
        # `ga4_events_18_...` isn't among them, so without a default dataset
        # BigQuery rejects it with "must be qualified with a dataset". Already
        # fully-qualified refs ignore the default, so this is harmless to them.
        job_config.default_dataset = f"{self._project}.{self._dataset}"
        start = time.time()
        job = self._bq().query(bound_sql, job_config=job_config)
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

    def _register_bronze_and_view(
        self,
        scope: OwnerScope,
        table: str,
        bronze_uri: str,
        bronze_prefix: str,
        schema: pa.Schema,
        unique_key: tuple[str, ...],
    ) -> None:
        """Register bronze external table over the `dt=*` glob and a silver
        view that returns the latest snapshot per `unique_key`.

        The user-facing fully-qualified name (`<scope-prefix>__<table>`)
        becomes the view; the audit-layer external table is suffixed
        `_bronze`. BQ doesn't permit a table and view to share a name —
        if a prior plain external table exists at the user-facing name
        (from before this feature), drop it first. That's metadata-only;
        no Parquet on GCS is touched.
        """
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        base = self._bq_table_name(scope, table)
        bronze_name = f"{base}_bronze"
        view_id = f"{self._project}.{self._dataset}.{base}"
        bronze_id = f"{self._project}.{self._dataset}.{bronze_name}"

        # 1. If a plain external table sits at the user-facing name, drop it
        # so a view can replace it. Idempotent — NotFound is the steady state.
        try:
            existing = self._bq().get_table(view_id)
            if existing.table_type != "VIEW":
                self._bq().delete_table(view_id)
                logger.info("Dropped plain external table %s to make room for dedup view", view_id)
        except NotFound:
            pass

        # 2. Register bronze external table at the dt=*/* glob. Hive AUTO so
        # `dt` is a queryable partition column (the view filters on it).
        # When `schema=` is supplied explicitly, BQ requires the Hive partition
        # column to be declared alongside the data columns — otherwise view
        # validation rejects references to `dt` at CREATE time with
        # `Unrecognized name: dt`, even though Hive AUTO would surface it at
        # query time.
        bq_schema = _arrow_schema_to_bq(schema)
        bq_schema.append(bigquery.SchemaField("dt", "DATE"))
        external_config = bigquery.ExternalConfig("PARQUET")
        external_config.source_uris = [bronze_uri]
        external_config.hive_partitioning = bigquery.HivePartitioningOptions()
        external_config.hive_partitioning.mode = "AUTO"
        external_config.hive_partitioning.source_uri_prefix = bronze_prefix.rstrip("/")

        bronze_table = bigquery.Table(bronze_id, schema=bq_schema)
        bronze_table.external_data_configuration = external_config
        try:
            self._bq().update_table(
                bronze_table,
                fields=["schema", "external_data_configuration"],
            )
        except NotFound:
            self._bq().create_table(bronze_table)
        logger.debug("Registered bronze external table %s", bronze_id)

        # 3. Create-or-replace the silver dedup view. ROW_NUMBER picks the
        # latest `dt=` partition per natural key. The view excludes the
        # internal `dt` and `_rn` columns so widget SQL sees only payload.
        keys = ", ".join(f"`{k}`" for k in unique_key)
        view_sql = (
            f"SELECT * EXCEPT(dt, _rn) FROM ("
            f"SELECT *, ROW_NUMBER() OVER (PARTITION BY {keys} ORDER BY dt DESC) AS _rn "
            f"FROM `{bronze_id}`"
            f") WHERE _rn = 1"
        )
        view_table = bigquery.Table(view_id)
        view_table.view_query = view_sql
        try:
            self._bq().update_table(view_table, fields=["view_query"])
        except NotFound:
            self._bq().create_table(view_table)
        self._invalidate_tables_memo(scope)
        logger.info(
            "Registered dedup view %s over %s (unique_key=%s)",
            view_id, bronze_id, unique_key,
        )

    def _merge_into_native(
        self,
        scope: OwnerScope,
        table: str,
        schema: pa.Schema,
        unique_key: tuple[str, ...],
        dt: str,
    ) -> None:
        """Upsert latest `dt=` snapshot into a native partitioned BQ table via MERGE.

        Replaces the bronze-external + silver-view pattern with a single native
        table: ingest-time dedup, partition + cluster pruning at query time,
        no per-widget ROW_NUMBER sort. The native table is the user-facing
        surface (`<scope_prefix>__<table>`); a transient staging external
        table (`<…>_stage`) sits over the freshest `dt=` Parquet only.

        Steps:
          1. Drop any prior view/external at the user-facing name (legacy
             cleanup, mirrors `_register_bronze_and_view`).
          2. `CREATE TABLE IF NOT EXISTS` native, partitioned by a date column
             (when one of {date_start, date, event_date, day} is `date32/64`)
             or ingestion-time DAY, clustered by `unique_key ∩ schema`.
          3. Register staging external table at `dt={dt}/*` (single partition).
          4. `MERGE` stage into native on `unique_key`.
        """
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        base = self._bq_table_name(scope, table)
        native_id = f"{self._project}.{self._dataset}.{base}"
        stage_id = f"{self._project}.{self._dataset}.{base}_stage"

        # 1. Drop any prior view or plain external table at the user-facing name
        # so the native table can take its place. Idempotent — NotFound is the
        # steady state. delete_table is metadata-only; Parquet on GCS untouched.
        try:
            existing = self._bq().get_table(native_id)
            if existing.table_type != "TABLE":
                self._bq().delete_table(native_id)
                logger.info(
                    "Dropped legacy %s %s to install native MERGE table",
                    existing.table_type, native_id,
                )
        except NotFound:
            pass

        bq_schema = _arrow_schema_to_bq(schema)
        partition_field = self._resolve_partition_field(schema)
        cluster_fields = self._resolve_cluster_fields(schema, unique_key)

        # 2. Create native table (idempotent). Partition + cluster lock in on
        # first create; subsequent runs are no-ops.
        native_table = bigquery.Table(native_id, schema=bq_schema)
        native_table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_field,
        )
        if cluster_fields:
            native_table.clustering_fields = list(cluster_fields)
        self._bq().create_table(native_table, exists_ok=True)
        self._invalidate_tables_memo(scope)

        # 3. (Re)register staging external table over the freshest `dt=` only.
        # No Hive partitioning — stage URI is anchored to a single dt directory.
        stage_uri = (
            f"gs://{self._bucket_name}/{self._gcs_prefix(scope, table, dt)}/*"
        )
        ext_cfg = bigquery.ExternalConfig("PARQUET")
        ext_cfg.source_uris = [stage_uri]
        stage_table = bigquery.Table(stage_id, schema=bq_schema)
        stage_table.external_data_configuration = ext_cfg
        try:
            self._bq().update_table(
                stage_table,
                fields=["schema", "external_data_configuration"],
            )
        except NotFound:
            self._bq().create_table(stage_table)

        # 4. MERGE. Skip key columns in the UPDATE SET (they're equal by the
        # ON clause); if every column is part of the key, omit WHEN MATCHED
        # entirely (BQ accepts MERGE with only WHEN NOT MATCHED).
        all_cols = [f.name for f in schema]
        key_set = set(unique_key)
        non_key_cols = [c for c in all_cols if c not in key_set]

        on_clause = " AND ".join(f"T.`{k}` = S.`{k}`" for k in unique_key)
        insert_cols = ", ".join(f"`{c}`" for c in all_cols)
        insert_vals = ", ".join(f"S.`{c}`" for c in all_cols)
        when_matched_clause = ""
        if non_key_cols:
            update_set = ", ".join(f"T.`{c}` = S.`{c}`" for c in non_key_cols)
            when_matched_clause = f"WHEN MATCHED THEN UPDATE SET {update_set}\n"

        merge_sql = (
            f"MERGE INTO `{native_id}` AS T\n"
            f"USING `{stage_id}` AS S\n"
            f"ON {on_clause}\n"
            f"{when_matched_clause}"
            f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})"
        )
        self._bq().query(merge_sql).result()
        logger.info(
            "MERGE'd %s into native table %s (unique_key=%s, partition=%s, cluster=%s)",
            stage_id, native_id, unique_key,
            partition_field or "_PARTITIONTIME", cluster_fields,
        )

    @staticmethod
    def _resolve_partition_field(schema: pa.Schema) -> str | None:
        """Pick the first date/timestamp column whose name matches a convention.

        Returns the column name for `PARTITION BY DATE(<field>)`, or None to
        fall back to ingestion-time partitioning.  BQ accepts both DATE and
        TIMESTAMP fields for DAY partitioning.
        """
        candidates = ("date_start", "date", "event_date", "day", "created_time", "last_edited_time")
        for name in candidates:
            if name not in schema.names:
                continue
            t = schema.field(name).type
            if t in (pa.date32(), pa.date64()):
                return name
            if pa.types.is_timestamp(t):
                return name
        return None

    @staticmethod
    def _resolve_cluster_fields(
        schema: pa.Schema,
        unique_key: tuple[str, ...],
    ) -> list[str]:
        """Cluster on the unique_key columns that actually exist in schema (max 4)."""
        available = set(schema.names)
        return [k for k in unique_key if k in available][:4]

    def list_tables(self, scope: OwnerScope, namespace: str | None = None) -> list[str]:
        memo_key = scope.as_path()
        cached = self._tables_memo.get(memo_key)
        if cached is not None and cached[0] > time.time():
            return list(cached[1])

        prefix = self._scope_bq_prefix(scope)
        tables = []
        for t in self._bq().list_tables(self._dataset):
            if t.table_id.startswith(prefix):
                # Strip the scope prefix to return bare table names
                bare = t.table_id[len(prefix):]
                # Hide internal audit/staging tables — callers see only the
                # user-facing name (view in legacy mode, native table in
                # native-merge mode).
                if bare.endswith("_bronze") or bare.endswith("_stage"):
                    continue
                tables.append(bare)
        self._tables_memo[memo_key] = (time.time() + _LIST_TABLES_TTL_S, list(tables))
        return tables

    def _invalidate_tables_memo(self, scope: OwnerScope) -> None:
        """Drop the listing memo for *scope* after creating a table in it.

        Without this a table registered inside the TTL window stays invisible to
        `_rewrite_sql`, which would leave a freshly-materialised table name
        unqualified and fail the next query against it.
        """
        self._tables_memo.pop(scope.as_path(), None)

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

    def read_dbt_model(self, scope: OwnerScope, model_name: str) -> pa.Table:
        """Read a dbt-materialized model out of the BigQuery dataset into Arrow.

        dbt (prod) materializes natively into `<project>.<dataset>.<model>`.
        Used by the GAP-3 step that lands dbt outputs in the GCS Parquet lake.
        """
        table_id = f"{self._project}.{self._dataset}.{model_name}"
        return self._bq().query(f"SELECT * FROM `{table_id}`").result().to_arrow()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _scope_bq_prefix(self, scope: OwnerScope) -> str:
        return scope.as_path().replace("/", "__") + "__"

    def _bq_table_name(self, scope: OwnerScope, table: str) -> str:
        safe_scope = scope.as_path().replace("/", "__")
        safe_table = table.replace("-", "_")
        return f"{safe_scope}__{safe_table}"

    def _rewrite_sql(self, scope: OwnerScope, sql: str) -> str:
        """Rewrite bare table names → fully-qualified BQ references, and
        Postgres-style double-quoted identifiers ("col") → BQ backtick
        identifiers (`col`).

        Filter injection (``backend.api.widget_data.inject_filters``) emits
        double-quoted identifiers because Postgres/MySQL accept them. BigQuery
        standard SQL treats ``"col"`` as a STRING LITERAL, which fails with
        ``Could not cast literal "col" to type DATE``. Convert any
        ``"<simple_identifier>"`` token to backticks. Non-identifier string
        literals (with spaces/punctuation) are left alone.
        """
        import re

        prefix = f"{self._project}.{self._dataset}."
        tables = self.list_tables(scope)
        result = sql
        for t in sorted(tables, key=len, reverse=True):  # longest first
            bq_name = self._bq_table_name(scope, t)
            target = f"`{prefix}{bq_name}`"
            # Already-backticked occurrences (LLM emits these now that the
            # dashboard agent prompt locks SQL to BigQuery dialect). Match
            # both bare `t` and schema-qualified `<schema>.t` inside backticks
            # — the dashboard agent's filter SQL parrots the sources hint
            # (e.g. `dataset.csv_40`) which BigQuery would otherwise parse
            # as a literal dataset name.
            result = re.sub(
                rf"`(?:main\.|public\.|dataset\.)?{re.escape(t)}`",
                target,
                result,
            )
            # Bare or schema-qualified occurrences. The lookbehind/ahead avoids
            # wrapping a table name that already sits inside a backticked FQN
            # like `proj.ds.scope__insights_daily` (which would otherwise produce
            # `` `proj.ds.scope__`...`insights_daily` `` ` → empty identifier).
            # `main.` / `public.` / `dataset.` prefixes are swallowed because
            # the dashboard agent's sources hint surfaces them from
            # SQLite/Postgres/CSV-origin connection contexts (the CSV plugin
            # hardcodes schema="dataset" in bingo_csv_connector/service.py);
            # leaving them in front of the rewritten FQN would make BigQuery
            # parse `main` / `public` / `dataset` as the project name.
            result = re.sub(
                rf"(?<![`\w])(?:main\.|public\.|dataset\.)?{re.escape(t)}(?![`\w])",
                target,
                result,
            )

        result = re.sub(
            r'"([A-Za-z_][A-Za-z0-9_]*)"',
            r"`\1`",
            result,
        )
        return result


# ---------------------------------------------------------------------------
# Arrow ↔ BigQuery schema conversion helpers
# ---------------------------------------------------------------------------

def _downcast_ns_timestamps(table: pa.Table) -> pa.Table:
    """BigQuery TIMESTAMP is microsecond precision; reject ns Parquet files.

    Cast any `timestamp[ns]` (or `timestamp[ns, tz]`) columns down to
    `timestamp[us]` (preserving tz) before write. Pandas defaults to
    `datetime64[ns]` so this triggers for almost every dataframe-sourced
    upload.
    """
    new_fields = []
    changed = False
    for f in table.schema:
        if pa.types.is_timestamp(f.type) and f.type.unit == "ns":
            new_fields.append(pa.field(f.name, pa.timestamp("us", tz=f.type.tz), nullable=f.nullable))
            changed = True
        else:
            new_fields.append(f)
    if not changed:
        return table
    return table.cast(pa.schema(new_fields))


# BigQuery rejects columns starting with any of these, case-insensitively.
# `_CHANGE_` covers the CDC pseudo-columns (`_CHANGE_TYPE`,
# `_CHANGE_SEQUENCE_NUMBER`, `_CHANGE_TIMESTAMP`) in one entry.
_BQ_RESERVED_PREFIXES = (
    "_TABLE_", "_FILE_", "_PARTITION", "_ROW_TIMESTAMP", "__ROOT__", "_COLIDENTIFIER",
    "_CHANGE_",
)


def bq_safe_column_names(table: pa.Table) -> tuple[pa.Table, dict[str, str]]:
    """Rename columns to names BigQuery accepts, returning `(table, rename_map)`.

    Guarantees each output name matches `[A-Za-z_][A-Za-z0-9_]{0,299}`, carries
    no BigQuery-reserved prefix, and is unique under BigQuery's case-insensitive
    column comparison.

    dlt names variant columns with its path separator (`value▶v_bool`), which
    BigQuery rejects when the external table is created — the whole load
    package then retries until the pipeline run fails. Rename before the
    Parquet write so the file and the BQ schema agree.

    When distinct source names collapse onto one safe name, *every* member of
    the colliding set gets a suffix hashed from its own original name — nobody
    wins the bare name by being first. So a given source column maps to the same
    safe name in every batch of a multi-batch load, whatever the column order.

    `rename_map` holds only the columns that changed. Callers must apply it to
    anything else that names columns (e.g. `unique_key`), or the Parquet file
    and the BQ surface built over it will disagree. Already-valid names are
    returned untouched, so this is a no-op for every existing table.
    """
    import hashlib
    import re
    from collections import Counter

    def base_of(name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if not safe or safe[0].isdigit():
            safe = "_" + safe
        if safe.upper().startswith(_BQ_RESERVED_PREFIXES):
            safe = "_" + safe
        return safe[:300]

    bases = [base_of(name) for name in table.schema.names]
    collisions = Counter(b.casefold() for b in bases)

    names: list[str] = []
    rename_map: dict[str, str] = {}
    for name, base in zip(table.schema.names, bases):
        if collisions[base.casefold()] > 1:
            base = f"{base[:293]}_{hashlib.sha1(name.encode()).hexdigest()[:6]}"
        names.append(base)
        if base != name:
            rename_map[name] = base
    if not rename_map:
        return table, {}
    logger.info("Renamed BigQuery-invalid column names: %s", sorted(rename_map.items()))
    return table.rename_columns(names), rename_map


def _arrow_schema_to_bq(schema: pa.Schema) -> list:
    from google.cloud.bigquery import SchemaField
    fields = []
    for field in schema:
        t = field.type
        if pa.types.is_integer(t):
            bq_type = "INT64"
        elif pa.types.is_floating(t):
            bq_type = "FLOAT64"
        elif pa.types.is_boolean(t):
            bq_type = "BOOL"
        elif pa.types.is_timestamp(t):
            bq_type = "TIMESTAMP"
        elif pa.types.is_date(t):
            bq_type = "DATE"
        elif pa.types.is_binary(t) or pa.types.is_large_binary(t):
            bq_type = "BYTES"
        elif pa.types.is_string(t) or pa.types.is_large_string(t):
            bq_type = "STRING"
        else:
            bq_type = "STRING"
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
