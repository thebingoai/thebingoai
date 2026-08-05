"""DataPlane Protocol — the interface every storage backend implements."""
from __future__ import annotations

from typing import Any, Iterator, Protocol, runtime_checkable

import pyarrow as pa

from backend.connectors.base import QueryResult, TableSchema
from .scope import OwnerScope


@runtime_checkable
class DataPlane(Protocol):
    """Pluggable data storage + query backend.

    All paths are scoped to an OwnerScope so different tenants never see each
    other's data even when sharing the same physical storage root.
    """

    def write_parquet(
        self,
        scope: OwnerScope,
        table: str,
        data: pa.Table | Iterator[pa.RecordBatch],
        mode: str = "overwrite",
        unique_key: tuple[str, ...] | None = None,
    ) -> None:
        """Write *data* as Hive-by-date Parquet at the scope-keyed path.

        When `unique_key` is provided, snapshot tables (`mode='overwrite'`)
        accumulate history across `dt=*` partitions and the plane exposes a
        dedup view selecting latest snapshot per key. When None, snapshot
        tables pin to the latest single `dt=` partition.
        """
        ...

    def register_table(
        self,
        scope: OwnerScope,
        table: str,
        path: str,
        schema: pa.Schema,
    ) -> None:
        """Engine-side table registration (e.g. BQ external table). No-op for local."""
        ...

    def put_raw_object(
        self,
        scope: OwnerScope,
        rel_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Store opaque bytes at a scope-relative path (non-Parquet sidecar storage,
        e.g. chat-attached raw CSV/XLSX). Each plane decides physical placement."""
        ...

    def get_raw_object(self, scope: OwnerScope, rel_path: str) -> bytes | None:
        """Read opaque bytes previously written by `put_raw_object`; None if absent."""
        ...

    def delete_raw_object(self, scope: OwnerScope, rel_path: str) -> None:
        """Delete the raw object at *rel_path*; silently no-op when absent."""
        ...

    def raw_object_exists(self, scope: OwnerScope, rel_path: str) -> bool:
        """Return True when a raw object exists at *rel_path*."""
        ...

    def query(
        self,
        scope: OwnerScope,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Run *sql* inside *scope*. Table names are scope-relative."""
        ...

    def read_table(self, scope: OwnerScope, table: str) -> QueryResult | None:
        """Read all rows of a table the caller already knows by name.

        None when the table does not exist. Distinct from `query()` on purpose:
        `query()` takes arbitrary SQL, so a plane may have to discover its whole
        namespace to resolve the identifiers in it — `BigQueryGCSPlane._rewrite_sql`
        lists the entire dataset on every call. A caller holding an exact table
        name must not pay for that, so implementations resolve the one name
        directly and make no metadata round-trip.
        """
        ...

    def list_tables(
        self,
        scope: OwnerScope,
        namespace: str | None = None,
    ) -> list[str]:
        """Return table names visible in *scope*."""
        ...

    def drop_table(self, scope: OwnerScope, table: str) -> None:
        """Delete all Parquet files for *table* within *scope*."""
        ...

    def table_exists(self, scope: OwnerScope, table: str) -> bool: ...

    def get_schema(self, scope: OwnerScope, table: str) -> pa.Schema: ...

    def storage_bytes(self, scope: OwnerScope) -> int:
        """Total bytes of stored Parquet data for *scope*. Best-effort: returns 0
        on a scan error rather than raising, so callers can degrade gracefully."""
        ...

    def to_dbt_profile(self) -> dict:
        """Return a dbt profiles.yml target config dict for this DataPlane.

        The dict is written directly under the profile's `outputs.default:` key.
        Keys vary by adapter:
          - dbt-duckdb: {"type": "duckdb", "path": "..."}
          - dbt-bigquery: {"type": "bigquery", "method": "service-account-json", ...}
        """
        ...
