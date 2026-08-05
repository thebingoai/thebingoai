from typing import ClassVar, Optional, Dict

import psycopg2
from psycopg2.extras import RealDictCursor
from backend.connectors.base import BaseConnector


class PostgresConnector(BaseConnector):
    """PostgreSQL database connector."""

    _db_type_name: ClassVar[str] = "PostgreSQL"
    _quote_char: ClassVar[str] = '"'
    _system_schemas: ClassVar[frozenset[str]] = frozenset(
        {"information_schema", "pg_catalog", "pg_toast"}
    )

    def _create_connection(self, **kwargs):
        """Create psycopg2 connection."""
        return psycopg2.connect(**kwargs)

    def _is_connection_alive(self, conn) -> bool:
        """Check if PostgreSQL connection is alive."""
        return conn is not None and not conn.closed

    def _get_cursor(self, conn, dict_mode: bool = False):
        """Get cursor (dict cursor for schema queries, tuple cursor for execute_query)."""
        if dict_mode:
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()

    def _get_connect_kwargs(self) -> dict:
        """Map properties to psycopg2 kwargs."""
        from backend.config import settings
        kwargs = {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.username,
            'password': self.password,
            # Bound connect + detect dead idle sockets fast (managed PG poolers
            # drop idle conns) so a stalled read doesn't hang past the 60s
            # frontend cap. Only test_connection had a connect_timeout before.
            'connect_timeout': settings.source_connect_timeout_s,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 3,
        }
        if self.ssl_enabled:
            ca_path = self._get_ca_cert_path()
            if ca_path:
                kwargs['sslmode'] = 'verify-ca'
                kwargs['sslrootcert'] = ca_path
            else:
                kwargs['sslmode'] = 'require'
        return kwargs

    def _begin_schema_read(self, cursor) -> None:
        """Cap the whole catalog read for this transaction.

        SET LOCAL, not a `-c statement_timeout` startup option: PgBouncer refuses
        `options` outright ("unsupported startup parameter"), which would stop
        every pooler-fronted source database from connecting at all, and even
        where a pooler accepts it a connection-level timeout persists on the
        server connection and leaks to the next client that borrows it.
        """
        from backend.config import settings
        cursor.execute(f"SET LOCAL statement_timeout = '{settings.query_timeout_ms}'")

    def _get_row_count(self, cursor, schema: str, table_name: str) -> int:
        """Use pg_class.reltuples (planner estimate, no scan). Falls back to an
        exact COUNT(*) when the table was never analyzed (reltuples <= 0)."""
        try:
            cursor.execute(
                "SELECT reltuples::bigint AS count FROM pg_class WHERE oid = %s::regclass",
                (f'"{schema}"."{table_name}"',),
            )
            row = cursor.fetchone()
            est = (row['count'] if isinstance(row, dict) else row[0]) if row else None
            if est is not None and est > 0:
                return int(est)
        except Exception:
            pass
        try:
            # Bounded by _begin_schema_read's SET LOCAL, which is still in force
            # for this transaction — this scan is what that cap exists for.
            return super()._get_row_count(cursor, schema, table_name)
        except Exception:
            # statement_timeout killed the scan, or the table vanished
            # mid-walk. The count is a display hint that is
            # never computed on (see BaseConnector._get_row_count), so degrade
            # instead of failing the whole schema refresh. Roll back first:
            # Postgres leaves the transaction ABORTED, and every later schema
            # query on this connection would die with 25P02.
            try:
                cursor.connection.rollback()
            except Exception:
                pass
            return 0

    def _get_column_comments(self, cursor, schema: str, table_name: str) -> Dict[str, str]:
        """Read column comments from ``pg_description`` (via ``col_description``)."""
        cursor.execute(
            """
            SELECT a.attname AS column_name, d.description AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            JOIN pg_description d ON d.objoid = c.oid AND d.objsubid = a.attnum
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table_name),
        )
        out: Dict[str, str] = {}
        for row in cursor.fetchall():
            name = row['column_name'] if isinstance(row, dict) else row[0]
            comment = row['comment'] if isinstance(row, dict) else row[1]
            if comment:
                out[name] = comment
        return out

    def _get_table_comment(self, cursor, schema: str, table_name: str) -> Optional[str]:
        """Read the table comment via ``obj_description``."""
        cursor.execute(
            """
            SELECT obj_description(c.oid) AS comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (schema, table_name),
        )
        row = cursor.fetchone()
        if not row:
            return None
        comment = row['comment'] if isinstance(row, dict) else row[0]
        return comment or None

    def _foreign_key_query(self, schema: str, table: str) -> tuple:
        """
        PostgreSQL FK query using constraint_column_usage.

        PostgreSQL's information_schema.key_column_usage lacks
        referenced_table_name/referenced_column_name (MySQL extensions).
        Must join with constraint_column_usage.
        """
        return ("""
            SELECT
                kcu.column_name as from_column,
                ccu.table_name as to_table,
                ccu.column_name as to_column
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.constraint_column_usage ccu
                ON kcu.constraint_name = ccu.constraint_name
                AND kcu.constraint_schema = ccu.constraint_schema
            WHERE kcu.table_schema = %s AND kcu.table_name = %s
              AND kcu.constraint_name IN (
                  SELECT constraint_name
                  FROM information_schema.table_constraints
                  WHERE constraint_type = 'FOREIGN KEY'
              )
        """, (schema, table))


def dlt_source_for(connection, extraction_config: dict | None = None):
    from backend.connectors.sql_dlt import sql_dlt_source
    return sql_dlt_source("postgresql+psycopg2", connection, extraction_config)


def fingerprint(connection) -> str:
    return f"postgres:{connection.host}:{connection.port}/{connection.database}"


def detect_partition_key(connector: "PostgresConnector", schema: str, table: str) -> str | None:
    """Return the first declarative partition-key column for *schema.table* or None.

    Targets PG 10+ declarative partitioning (`pg_partitioned_table`). Inheritance
    partitioning and partitioned children are ignored — only parent tables match.
    Any failure (insufficient permissions, query error) returns None silently.
    """
    if not schema:
        schema = "public"
    sql = """
        SELECT a.attname
        FROM pg_partitioned_table pt
        JOIN pg_class c ON c.oid = pt.partrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = pt.partrelid AND a.attnum = ANY(pt.partattrs::int[])
        WHERE n.nspname = %s AND c.relname = %s
        ORDER BY a.attnum
        LIMIT 1
    """
    conn = None
    try:
        conn = connector._get_connection()
        cur = connector._get_cursor(conn, dict_mode=False)
        cur.execute(sql, (schema, table))
        row = cur.fetchone()
        cur.close()
        if row:
            return row[0]
    except Exception:
        return None
    return None
