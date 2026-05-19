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

    def query(
        self,
        scope: OwnerScope,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> QueryResult:
        """Run *sql* inside *scope*. Table names are scope-relative."""
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

    def to_dbt_profile(self) -> dict:
        """Return a dbt profiles.yml target config dict for this DataPlane.

        The dict is written directly under the profile's `outputs.default:` key.
        Keys vary by adapter:
          - dbt-duckdb: {"type": "duckdb", "path": "..."}
          - dbt-bigquery: {"type": "bigquery", "method": "service-account-json", ...}
        """
        ...
