import psycopg2
from psycopg2.extras import RealDictCursor
from backend.connectors.base import BaseConnector


class PostgresConnector(BaseConnector):
    """
    PostgreSQL database connector.

    Implements ~45 lines by leveraging BaseConnector template methods.
    Only provides database-specific primitives and hooks.
    """

    # ============================================================
    # Abstract Primitives (required by BaseConnector)
    # ============================================================

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

    def _quote_identifier(self, name: str) -> str:
        """Quote identifier with double quotes for PostgreSQL."""
        # Escape embedded double quotes by doubling them
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    @classmethod
    def _db_type_name(cls) -> str:
        """Return database type name."""
        return "PostgreSQL"

    @classmethod
    def _default_port(cls) -> int:
        return 5432

    @classmethod
    def _description(cls) -> str:
        return "Open-source relational database"

    @classmethod
    def _badge_variant(cls) -> str:
        return "info"

    # ============================================================
    # Overridable Hooks (customize for PostgreSQL)
    # ============================================================

    def _default_schema(self) -> str:
        """PostgreSQL default schema."""
        return "public"

    def _system_schemas(self) -> set:
        """PostgreSQL system schemas to exclude."""
        return {"information_schema", "pg_catalog", "pg_toast"}

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
