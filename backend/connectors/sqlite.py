import os
import re
import sqlite3
import time
import logging
from typing import Dict, List, Optional

from backend.connectors.base import QueryResult, TableSchema

logger = logging.getLogger(__name__)

_SQLITE_TO_PG = {
    "INTEGER": "BIGINT",
    "REAL": "DOUBLE PRECISION",
    "TEXT": "TEXT",
    "BLOB": "TEXT",
    "NUMERIC": "DOUBLE PRECISION",
}


def _sqlite_to_pg_type(sqlite_type: str) -> str:
    """Map SQLite column type to PostgreSQL-style type for schema consistency."""
    return _SQLITE_TO_PG.get(sqlite_type.upper(), "TEXT")


class SqliteFileConnector:
    """SQLite file-based connector for uploaded .sqlite/.db databases."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    @classmethod
    def from_connection(cls, connection, db_session=None) -> "SqliteFileConnector":
        """
        Download (or use cached) SQLite file from DO Spaces and return a connector.

        The DO Spaces key is stored in connection.dataset_table_name.
        The file is cached locally for up to 1 hour.

        If ``db_session`` is provided and the download fails (file missing in
        DO Spaces), the connection's ``health_status`` is set to ``"unhealthy"``
        before the error is raised.
        """
        from backend.services import object_storage
        from backend.config import settings

        do_spaces_key = connection.dataset_table_name
        cache_dir = settings.dataset_cache_dir
        cache_path = os.path.join(cache_dir, f"{connection.id}.sqlite")

        cache_valid = (
            os.path.exists(cache_path)
            and os.path.getmtime(cache_path) > time.time() - 3600
        )

        if not cache_valid:
            data = object_storage.download_bytes(do_spaces_key)
            if data is None:
                if db_session is not None:
                    from datetime import datetime, timezone
                    connection.health_status = "unhealthy"
                    connection.health_checked_at = datetime.now(timezone.utc)
                    db_session.commit()
                raise FileNotFoundError(
                    f"SQLite file not found in DO Spaces: {do_spaces_key}"
                )
            os.makedirs(cache_dir, exist_ok=True)
            tmp_path = cache_path + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(data)
            os.rename(tmp_path, cache_path)

        return cls(cache_path)

    def test_connection(self) -> bool:
        """Test if the SQLite file is valid and has at least one user table."""
        try:
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                tables = cursor.fetchall()
                if not tables:
                    raise ConnectionError("SQLite database has no user tables")
                return True
            finally:
                conn.close()
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect to SQLite database: {e}")

    def get_schemas(self) -> List[str]:
        """SQLite has a single schema."""
        return ["main"]

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        """Get list of user tables in the SQLite database."""
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_table_schema(self, table_name: str, schema: Optional[str] = None) -> TableSchema:
        """Get detailed schema for a table using PRAGMA table_info."""
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
            columns = []
            for row in cursor.fetchall():
                # PRAGMA table_info returns: (cid, name, type, notnull, dflt_value, pk)
                columns.append({
                    "name": row[1],
                    "type": _sqlite_to_pg_type(row[2]),
                    "nullable": not row[3],
                    "primary_key": bool(row[5]),
                })

            cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]

            return TableSchema(
                table_name=table_name,
                columns=columns,
                row_count=row_count,
            )
        finally:
            conn.close()

    def get_foreign_keys(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, str]]:
        """Get foreign key relationships using PRAGMA foreign_key_list."""
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cursor = conn.execute(f'PRAGMA foreign_key_list("{table_name}")')
            fks = []
            for row in cursor.fetchall():
                # PRAGMA foreign_key_list returns: (id, seq, table, from, to, on_update, on_delete, match)
                fks.append({
                    "from_column": row[3],
                    "to_table": row[2],
                    "to_column": row[4],
                })
            return fks
        finally:
            conn.close()

    def execute_query(self, query: str, params=None) -> QueryResult:
        """Execute a read-only SELECT query against the SQLite database."""
        self._validate_readonly_query(query)

        start_time = time.time()
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cursor = conn.cursor()
            if params:
                if isinstance(params, dict):
                    ordered_keys = re.findall(r'%\((\w+)\)s', query)
                    if ordered_keys:
                        query = re.sub(r'%\(\w+\)s', '?', query)
                        params = [params[k] for k in ordered_keys]
                    else:
                        params = list(params.values())
                    query = re.sub(r'\bILIKE\b', 'LIKE', query, flags=re.IGNORECASE)
                cursor.execute(query, params)
            else:
                query = re.sub(r'\bILIKE\b', 'LIKE', query, flags=re.IGNORECASE)
                cursor.execute(query)

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            from backend.config import settings
            max_rows = settings.max_query_rows
            rows = cursor.fetchmany(max_rows + 1)
            truncated = len(rows) > max_rows
            if truncated:
                rows = rows[:max_rows]

            execution_time_ms = (time.time() - start_time) * 1000
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_time_ms=execution_time_ms,
                truncated=truncated,
            )
        finally:
            conn.close()

    def _validate_readonly_query(self, query: str) -> None:
        """Validate that query is read-only (SELECT/WITH only)."""
        query_upper = query.strip().upper()

        if len(query) > 10_000:
            raise ValueError("Query exceeds maximum allowed length of 10,000 characters.")

        lines = [line.split('--')[0] for line in query_upper.split('\n')]
        query_clean = ' '.join(lines)
        query_clean = re.sub(r'/\*.*?\*/', ' ', query_clean, flags=re.DOTALL)
        query_clean = ' '.join(query_clean.split())

        if ';' in query_clean.rstrip(';'):
            raise ValueError("Multiple statements not allowed. Only single SELECT queries permitted.")

        # Strip quoted identifiers and string literals so column names
        # like "cluster" don't trigger the dangerous-keyword check.
        query_for_keyword_check = re.sub(r'"[^"]*"', ' ', query_clean)
        query_for_keyword_check = re.sub(r"'[^']*'", ' ', query_for_keyword_check)

        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
            'COPY', 'LOAD', 'SET', 'CALL', 'RENAME',
            'INTO', 'EXPLAIN', 'VACUUM', 'REINDEX', 'CLUSTER',
            'COMMENT', 'NOTIFY', 'LISTEN', 'UNLISTEN', 'DO',
            'PREPARE', 'DEALLOCATE',
        ]
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', query_for_keyword_check):
                raise ValueError(f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed.")

        dangerous_sqlite_functions = [
            r'\bLOAD_EXTENSION\b', r'\bREADFILE\b', r'\bWRITEFILE\b',
        ]
        for pattern in dangerous_sqlite_functions:
            if re.search(pattern, query_clean):
                raise ValueError("Query contains a forbidden SQLite function.")

        if not re.match(r'^(SELECT|WITH)\b', query_clean):
            raise ValueError("Query must start with SELECT or WITH (for CTEs)")

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
