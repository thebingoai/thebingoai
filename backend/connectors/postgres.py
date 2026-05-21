from typing import ClassVar

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
        kwargs = {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.username,
            'password': self.password
        }
        if self.ssl_enabled:
            ca_path = self._get_ca_cert_path()
            if ca_path:
                kwargs['sslmode'] = 'verify-ca'
                kwargs['sslrootcert'] = ca_path
            else:
                kwargs['sslmode'] = 'require'
        return kwargs

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
