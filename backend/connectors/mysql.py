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


import re as _re

_FUNC_COL_RE = _re.compile(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\s*[`\"]?([A-Za-z_][A-Za-z0-9_]*)[`\"]?\s*\)\s*$")
_BARE_COL_RE = _re.compile(r"^\s*[`\"]?([A-Za-z_][A-Za-z0-9_]*)[`\"]?\s*$")


def _parse_partition_expression(expr: str | None) -> str | None:
    """Parse a MySQL PARTITION_EXPRESSION down to a single column name.

    Handles bare `col` and one-level wraps `FUNC(col)` (TO_DAYS, YEAR, MONTH,
    UNIX_TIMESTAMP, etc.). Hash, list-by-expression, multi-column composites
    return None.
    """
    if not expr:
        return None
    m = _BARE_COL_RE.match(expr)
    if m:
        return m.group(1)
    m = _FUNC_COL_RE.match(expr)
    if m:
        return m.group(1)
    return None


def detect_partition_key(connector: "MySQLConnector", schema: str, table: str) -> str | None:
    """Return the partition-key column for a MySQL range/list-partitioned table or None.

    Reads `INFORMATION_SCHEMA.PARTITIONS.PARTITION_EXPRESSION` and parses the
    expression with `_parse_partition_expression`. Any failure returns None
    silently — partition detection is best-effort and should not break ingestion
    scaffolding.
    """
    if not schema:
        schema = connector.database
    sql = """
        SELECT PARTITION_EXPRESSION, PARTITION_METHOD
        FROM INFORMATION_SCHEMA.PARTITIONS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND PARTITION_METHOD IS NOT NULL
        LIMIT 1
    """
    conn = None
    try:
        conn = connector._get_connection()
        cur = connector._get_cursor(conn, dict_mode=False)
        cur.execute(sql, (schema, table))
        row = cur.fetchone()
        cur.close()
    except Exception:
        return None
    if not row:
        return None
    expr = row[0] if not isinstance(row, dict) else row.get("partition_expression")
    return _parse_partition_expression(expr)
