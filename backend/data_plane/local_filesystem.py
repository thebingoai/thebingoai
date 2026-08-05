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
import threading

from backend.connectors.base import QueryResult, TableSchema
from .scope import OwnerScope

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = "/data/data_plane"


class LocalFilesystemDataPlane:
    """DataPlane backed by a local filesystem volume + embedded DuckDB."""

    def __init__(self, root_path: str = _DEFAULT_ROOT) -> None:
        self._root = root_path
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._conn_lock = threading.RLock()
        self._loaded_tables: set[tuple[str, str]] = set()

    # ── Internal path helpers ─────────────────────────────────────────────

    def _scope_root(self, scope: OwnerScope) -> str:
        return os.path.join(self._root, scope.as_path())

    def _table_root(self, scope: OwnerScope, table: str) -> str:
        return os.path.join(self._scope_root(scope), table)

    def _raw_path(self, scope: OwnerScope, rel_path: str) -> str:
        # Sibling `_raw/` namespace — kept OUT of `_scope_root` so raw objects
        # never appear in `list_tables` / `_register_scope_views` (which walk
        # the scope root and treat every dir as a Parquet table).
        return os.path.join(self._root, "_raw", scope.as_path(), rel_path)

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

    # ── Dedup-key sidecar ─────────────────────────────────────────────────

    def _meta_path(self, scope: OwnerScope, table: str) -> str:
        return os.path.join(self._table_root(scope, table), "_meta.json")

    def _write_meta(self, scope: OwnerScope, table: str, unique_key: tuple[str, ...]) -> None:
        import json
        path = self._meta_path(scope, table)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"unique_key": list(unique_key)}, f)
        os.rename(tmp, path)

    def _read_unique_key(self, scope: OwnerScope, table: str) -> tuple[str, ...] | None:
        import json
        path = self._meta_path(scope, table)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as f:
                uk = json.load(f).get("unique_key")
        except (OSError, ValueError):
            return None
        return tuple(uk) if uk else None

    def _resolve_view_key(self, scope: OwnerScope, table: str) -> tuple[str, ...] | None:
        """Stored unique_key intersected with the table's actual Parquet columns.

        Falls back to None (raw-union view) when no key is stored, no partition
        exists yet, or none of the key columns are present — so an invalid
        `PARTITION BY` is never emitted.
        """
        unique_key = self._read_unique_key(scope, table)
        if not unique_key:
            return None
        latest = self._latest_partition(scope, table)
        if latest is None:
            return None
        parquet_files = [f for f in os.listdir(latest) if f.endswith(".parquet")]
        if not parquet_files:
            return None
        cols = set(pq.read_schema(os.path.join(latest, parquet_files[0])).names)
        filtered = tuple(k for k in unique_key if k in cols)
        return filtered or None

    # ── DuckDB connection ─────────────────────────────────────────────────

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        with self._conn_lock:
            if self._conn is None:
                from .duckdb_exec import apply_memory_guardrails
                self._conn = duckdb.connect()
                apply_memory_guardrails(self._conn)
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
        import uuid
        dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        partition_dir = self._partition_dir(scope, table, dt)

        if mode == "overwrite" and os.path.isdir(partition_dir):
            shutil.rmtree(partition_dir)

        os.makedirs(partition_dir, exist_ok=True)

        # Persist the dedup key beside the data so `_register_scope_views` can
        # build a latest-`dt`-per-key view (parity with BigQueryGCSPlane's
        # silver view). Sidecar sits in the table root, not a `dt=` dir, so it
        # never enters the `dt=*/*.parquet` glob or `list_tables`.
        if unique_key:
            self._write_meta(scope, table, unique_key)

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
        self.invalidate_table(scope, table)

    def register_table(self, scope: OwnerScope, table: str, path: str, schema: pa.Schema) -> None:
        pass  # no-op for local: DuckDB reads files directly

    def put_raw_object(
        self,
        scope: OwnerScope,
        rel_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Store opaque bytes at a scope-relative path (non-Parquet sidecar storage)."""
        path = self._raw_path(scope, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.rename(tmp, path)  # atomic on same FS, matches write_parquet

    def get_raw_object(self, scope: OwnerScope, rel_path: str) -> bytes | None:
        """Read opaque bytes at a scope-relative path; None if absent."""
        path = self._raw_path(scope, rel_path)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def delete_raw_object(self, scope: OwnerScope, rel_path: str) -> None:
        """Delete the raw object at *rel_path*; silently no-op when absent."""
        try:
            os.remove(self._raw_path(scope, rel_path))
        except FileNotFoundError:
            pass

    def raw_object_exists(self, scope: OwnerScope, rel_path: str) -> bool:
        """Return True when a raw object exists at *rel_path*."""
        return os.path.isfile(self._raw_path(scope, rel_path))

    def query(
        self,
        scope: OwnerScope,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        from .duckdb_exec import run_duckdb_query

        with self._conn_lock:
            conn = self._get_conn()
            self._register_scope_views(conn, scope)
            return run_duckdb_query(conn, sql, params)

    def read_table(self, scope: OwnerScope, table: str) -> QueryResult | None:
        """Read one known table; None when it does not exist.

        Local resolution is a stat of the scope directory, so unlike the
        BigQuery plane there is nothing to save here — this keeps the two
        planes' contract identical.
        """
        if not self.table_exists(scope, table):
            return None
        return self.query(scope, f'SELECT * FROM "{table}"')

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

    def storage_bytes(self, scope: OwnerScope) -> int:
        # Best-effort per the DataPlane contract: any scan error degrades to 0
        # rather than propagating (matches BigQueryGCSPlane.storage_bytes).
        try:
            scope_root = self._scope_root(scope)
            if not os.path.isdir(scope_root):
                return 0
            total = 0
            for dirpath, _dirs, files in os.walk(scope_root):
                for f in files:
                    if not f.endswith(".parquet"):
                        continue
                    try:
                        total += os.path.getsize(os.path.join(dirpath, f))
                    except OSError:
                        pass
            return total
        except Exception:
            logger.warning("storage_bytes scan failed for %s", scope, exc_info=True)
            return 0

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
            from .duckdb_exec import apply_memory_guardrails
            apply_memory_guardrails(conn)
            return conn.execute(f'SELECT * FROM "{model_name}"').fetch_arrow_table()
        finally:
            conn.close()

    # ── Internal helpers ──────────────────────────────────────────────────

    def invalidate_table(self, scope: OwnerScope, table: str) -> None:
        """Drop the in-memory table for *scope/table* so it is reloaded on next query.

        Called after a Parquet write so cached agents see fresh data.
        """
        key = (scope.as_path(), table)
        self._loaded_tables.discard(key)
        if self._conn is not None:
            safe = table.replace("-", "_")
            try:
                self._conn.execute(f"DROP TABLE IF EXISTS {safe}")
            except Exception:
                pass

    def _register_scope_views(self, conn: duckdb.DuckDBPyConnection, scope: OwnerScope) -> None:
        """Materialize each scope table into an in-memory DuckDB TABLE on first access.

        Uses TABLE (not VIEW) so subsequent queries read from RAM, not Parquet on disk.
        The _loaded_tables set prevents re-loading on every query call.
        """
        from .duckdb_exec import build_scope_view_sql

        scope_root = self._scope_root(scope)
        if not os.path.isdir(scope_root):
            return
        for table in os.listdir(scope_root):
            table_root = os.path.join(scope_root, table)
            if not os.path.isdir(table_root):
                continue
            cache_key = (scope.as_path(), table)
            if cache_key in self._loaded_tables:
                continue
            glob_pattern = os.path.join(table_root, "dt=*", "*.parquet")
            unique_key = self._resolve_view_key(scope, table)
            view_sql = build_scope_view_sql(table, glob_pattern, unique_key)
            table_sql = view_sql.replace("CREATE OR REPLACE VIEW ", "CREATE OR REPLACE TABLE ", 1)
            conn.execute(table_sql)
            self._loaded_tables.add(cache_key)
