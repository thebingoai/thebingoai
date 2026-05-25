"""DuckDB-over-GCS reader (Phase 2).

Serves widget reads by running already-DuckDB SQL over the per-Org GCS Parquet
**directly via httpfs** — no synced copy. Prod analog of
`LocalFilesystemDataPlane`: register one view per referenced table over its
`gs://…/dt=*` glob, then run the query through the shared `run_duckdb_query`
(same binding + row-cap as the local plane).

Auth: DuckDB httpfs reads GCS via an **HMAC** interop key (KEY_ID/SECRET), not
the service-account JSON the plane holds. HMAC keys are provisioned for the
internal SA and supplied via settings (see `internal_gcs_hmac_*`).
"""
from __future__ import annotations

import logging
from typing import Any

from backend.connectors.base import QueryResult
from .scope import OwnerScope

logger = logging.getLogger(__name__)


def _secret_sql(key_id: str, secret: str) -> str:
    """CREATE-SECRET DDL for DuckDB's GCS provider (HMAC interop key).

    Idempotent per connection via OR REPLACE. Credentials are server-side
    config, never user input.
    """
    if "'" in key_id or "'" in secret:
        raise ValueError("GCS HMAC credentials must not contain single quotes")
    return f"CREATE OR REPLACE SECRET bingo_gcs (TYPE GCS, KEY_ID '{key_id}', SECRET '{secret}')"


def _view_sql(table: str, glob: str, unique_key: tuple[str, ...] | None = None) -> str:
    """CREATE-VIEW DDL exposing a table's GCS Parquet under its bare name.

    Delegates to the shared `duckdb_exec.build_scope_view_sql` so dev
    (`LocalFilesystemDataPlane`) and prod (this reader) share one view
    definition. *unique_key* is None today (no GCS sidecar reader yet); once
    Phase 2 sources it, this path dedups to the latest `dt=` per key for free.
    """
    from .duckdb_exec import build_scope_view_sql

    return build_scope_view_sql(table, glob, unique_key)


class GCSDuckDBReader:
    """Runs DuckDB SQL over an Org's GCS Parquet via httpfs.

    One reader per (bucket, scope chain) per task; close after use. Views are
    (re)registered per query for the tables the SQL references.
    """

    def __init__(self, bucket: str, hmac_key_id: str, hmac_secret: str) -> None:
        self._bucket = bucket
        self._key_id = hmac_key_id
        self._secret = hmac_secret
        self._conn = None

    def _get_conn(self):
        if self._conn is None:
            import duckdb

            conn = duckdb.connect()
            conn.execute("INSTALL httpfs")
            conn.execute("LOAD httpfs")
            conn.execute(_secret_sql(self._key_id, self._secret))
            self._conn = conn
        return self._conn

    def query(self, scope: OwnerScope, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
        from backend.utils.sql_refs import extract_table_refs
        from .bigquery_gcs import gcs_parquet_glob
        from .duckdb_exec import run_duckdb_query

        conn = self._get_conn()
        for table in extract_table_refs(sql):
            glob = gcs_parquet_glob(self._bucket, scope, table)
            conn.execute(_view_sql(table, glob))
        return run_duckdb_query(conn, sql, params)

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
