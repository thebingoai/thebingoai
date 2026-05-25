"""LocalFilesystemDataPlane — Parquet on a local Docker volume, queried via DuckDB.

Atomic writes: stage to <path>.tmp → os.rename (POSIX atomic on same filesystem).
DuckDB connection lifecycle (P1.2): one connection per task, opened on first query,
closed explicitly. The caller is responsible for closing after each Celery task.
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from backend.connectors.base import QueryResult, TableSchema
from .scope import OwnerScope

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = "/data/data_plane"


class LocalFilesystemDataPlane:
    """DataPlane backed by a local filesystem volume + embedded DuckDB."""

    def __init__(self, root_path: str = _DEFAULT_ROOT) -> None:
        self._root = root_path
        self._conn: duckdb.DuckDBPyConnection | None = None

    # ── Internal path helpers ─────────────────────────────────────────────

    def _scope_root(self, scope: OwnerScope) -> str:
        return os.path.join(self._root, scope.as_path())

    def _table_root(self, scope: OwnerScope, table: str) -> str:
        return os.path.join(self._scope_root(scope), table)

    def _partition_dir(self, scope: OwnerScope, table: str, dt: str | None = None) -> str:
        if dt is None:
            dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return os.path.join(self._table_root(scope, table), f"dt={dt}")

    def _latest_partition(self, scope: OwnerScope, table: str) -> str | None:
        table_root = self._table_root(scope, table)
        if not os.path.isdir(table_root):
            return None
        partitions = sorted(
            [d for d in os.listdir(table_root) if d.startswith("dt=")],
            reverse=True,
        )
        return os.path.join(table_root, partitions[0]) if partitions else None

    # ── DuckDB connection ─────────────────────────────────────────────────

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── DataPlane interface ───────────────────────────────────────────────

    def write_parquet(
        self,
        scope: OwnerScope,
        table: str,
        data: pa.Table | Iterator[pa.RecordBatch],
        mode: str = "overwrite",
        unique_key: tuple[str, ...] | None = None,
    ) -> None:
        # unique_key is accepted for protocol compatibility but not yet honored
        # in local-filesystem mode (DuckDB views could implement dedup-at-read
        # later). Local-fs is dev-only; production uses BigQueryGCSPlane.
        _ = unique_key
        import uuid
        dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        partition_dir = self._partition_dir(scope, table, dt)

        if mode == "overwrite" and os.path.isdir(partition_dir):
            shutil.rmtree(partition_dir)

        os.makedirs(partition_dir, exist_ok=True)

        # Unique part suffix per call for append/merge so multi-batch dlt loads
        # accumulate. Overwrite stays at part-0 (dir is wiped above).
        part_id = "0" if mode == "overwrite" else uuid.uuid4().hex[:12]
        part_path = os.path.join(partition_dir, f"part-{part_id}.parquet")
        tmp_path = part_path + ".tmp"
        try:
            if isinstance(data, pa.Table):
                pq.write_table(data, tmp_path)
            else:
                writer = None
                try:
                    for batch in data:
                        if writer is None:
                            writer = pq.ParquetWriter(tmp_path, batch.schema)
                        writer.write_batch(batch)
                finally:
                    if writer:
                        writer.close()
            os.rename(tmp_path, part_path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

        logger.debug("Wrote parquet %s → %s", table, part_path)

    def register_table(self, scope: OwnerScope, table: str, path: str, schema: pa.Schema) -> None:
        pass  # no-op for local: DuckDB reads files directly

    def query(
        self,
        scope: OwnerScope,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        from .duckdb_exec import run_duckdb_query

        conn = self._get_conn()
        self._register_scope_views(conn, scope)
        return run_duckdb_query(conn, sql, params)

    def list_tables(self, scope: OwnerScope, namespace: str | None = None) -> list[str]:
        scope_root = self._scope_root(scope)
        if not os.path.isdir(scope_root):
            return []
        tables = []
        for entry in os.listdir(scope_root):
            if os.path.isdir(os.path.join(scope_root, entry)):
                tables.append(entry)
        return tables

    def drop_table(self, scope: OwnerScope, table: str) -> None:
        table_root = self._table_root(scope, table)
        if os.path.isdir(table_root):
            shutil.rmtree(table_root)

    def table_exists(self, scope: OwnerScope, table: str) -> bool:
        latest = self._latest_partition(scope, table)
        if latest is None:
            return False
        return any(f.endswith(".parquet") for f in os.listdir(latest))

    def to_dbt_profile(self) -> dict:
        return {
            "type": "duckdb",
            "path": "{duckdb_path}",   # synthesizer substitutes the real path
            "threads": 2,
        }

    def get_schema(self, scope: OwnerScope, table: str) -> pa.Schema:
        latest = self._latest_partition(scope, table)
        if latest is None:
            raise FileNotFoundError(f"Table {table!r} not found in scope {scope}")
        parquet_files = [f for f in os.listdir(latest) if f.endswith(".parquet")]
        if not parquet_files:
            raise FileNotFoundError(f"No parquet files in {latest}")
        return pq.read_schema(os.path.join(latest, parquet_files[0]))

    def read_dbt_model(self, scope: OwnerScope, model_name: str) -> pa.Table:
        """Read a dbt-materialized model out of the per-scope DuckDB store into Arrow.

        dbt (dev) materializes natively into `<root>/<scope>/dbt.duckdb`
        (`project_synth` points the duckdb profile there). Used by the GAP-3
        step that lands dbt outputs in the DataPlane Parquet lake.
        """
        dbt_path = os.path.join(self._scope_root(scope), "dbt.duckdb")
        if not os.path.exists(dbt_path):
            raise FileNotFoundError(f"dbt duckdb store not found: {dbt_path}")
        conn = duckdb.connect(dbt_path, read_only=True)
        try:
            return conn.execute(f'SELECT * FROM "{model_name}"').fetch_arrow_table()
        finally:
            conn.close()

    # ── Internal helpers ──────────────────────────────────────────────────

    def _register_scope_views(self, conn: duckdb.DuckDBPyConnection, scope: OwnerScope) -> None:
        """Create/replace DuckDB VIEWs for every table in scope so SQL can use bare names."""
        scope_root = self._scope_root(scope)
        if not os.path.isdir(scope_root):
            return
        for table in os.listdir(scope_root):
            table_root = os.path.join(scope_root, table)
            if not os.path.isdir(table_root):
                continue
            glob_pattern = os.path.join(table_root, "dt=*", "*.parquet")
            safe = table.replace("-", "_")
            conn.execute(
                f"CREATE OR REPLACE VIEW {safe} AS "
                f"SELECT * FROM read_parquet({glob_pattern!r}, hive_partitioning=true)"
            )
