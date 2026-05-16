from typing import ClassVar

import pymysql
from pymysql.cursors import DictCursor
from backend.connectors.base import BaseConnector


class _LowercaseDictCursor(DictCursor):
    """DictCursor that lowercases column names so the base connector's
    case-sensitive lookups (e.g. row['schema_name']) work against MySQL
    information_schema (which returns names like SCHEMA_NAME)."""

    def _conv_row(self, row):
        if row is None:
            return None
        return self.dict_type(zip([f.lower() for f in self._fields], row))


class MySQLConnector(BaseConnector):
    """
    MySQL database connector.

    Uses default FK query from BaseConnector (MySQL information_schema supports it).
    """

    _db_type_name: ClassVar[str] = "MySQL"
    _quote_char: ClassVar[str] = "`"
    _system_schemas: ClassVar[frozenset[str]] = frozenset(
        {"information_schema", "mysql", "performance_schema", "sys"}
    )

    def _create_connection(self, **kwargs):
        """Create PyMySQL connection."""
        return pymysql.connect(**kwargs)

    def _is_connection_alive(self, conn) -> bool:
        """Check if MySQL connection is alive."""
        return conn is not None and conn.open

    def _get_cursor(self, conn, dict_mode: bool = False):
        """Get cursor (dict cursor for schema queries, tuple cursor for execute_query)."""
        if dict_mode:
            return conn.cursor(_LowercaseDictCursor)
        return conn.cursor()

    def _get_connect_kwargs(self) -> dict:
        """Map properties to PyMySQL kwargs."""
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
                kwargs['ssl'] = {'ca': ca_path}
            else:
                kwargs['ssl'] = {'ssl': True}
            kwargs['ssl_disabled'] = False
        return kwargs

    def _default_schema(self) -> str:
        """MySQL default schema is the connected database."""
        return self.database


def dlt_source_for(connection, extraction_config: dict | None = None):
    from backend.connectors.sql_dlt import sql_dlt_source
    return sql_dlt_source("mysql+pymysql", connection, extraction_config)


def fingerprint(connection) -> str:
    return f"mysql:{connection.host}:{connection.port}/{connection.database}"
