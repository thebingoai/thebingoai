import pymysql
from pymysql.cursors import DictCursor
from backend.connectors.base import BaseConnector


class MySQLConnector(BaseConnector):
    """
    MySQL database connector.

    Implements ~35 lines by leveraging BaseConnector template methods.
    Uses default FK query from BaseConnector (MySQL information_schema supports it).
    """

    # ============================================================
    # Abstract Primitives (required by BaseConnector)
    # ============================================================

    def _create_connection(self, **kwargs):
        """Create PyMySQL connection."""
        return pymysql.connect(**kwargs)

    def _is_connection_alive(self, conn) -> bool:
        """Check if MySQL connection is alive."""
        return conn is not None and conn.open

    def _get_cursor(self, conn, dict_mode: bool = False):
        """Get cursor (dict cursor for schema queries, tuple cursor for execute_query)."""
        if dict_mode:
            return conn.cursor(DictCursor)
        return conn.cursor()

    def _get_connect_kwargs(self) -> dict:
        """Map properties to PyMySQL kwargs."""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.username,
            'password': self.password
        }

    def _quote_identifier(self, name: str) -> str:
        """Quote identifier with backticks for MySQL."""
        return f'`{name}`'

    def _db_type_name(self) -> str:
        """Return database type name."""
        return "MySQL"

    # ============================================================
    # Overridable Hooks (customize for MySQL)
    # ============================================================

    def _default_schema(self) -> str:
        """MySQL default schema is the connected database."""
        return self.database

    def _system_schemas(self) -> set:
        """MySQL system schemas to exclude."""
        return {"information_schema", "mysql", "performance_schema", "sys"}

    # Note: _foreign_key_query() uses default from BaseConnector
    # (MySQL information_schema has referenced_table_name/referenced_column_name)
