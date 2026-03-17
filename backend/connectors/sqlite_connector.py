import sqlite3
import time
import re
import logging
from backend.connectors.base import QueryResult

logger = logging.getLogger(__name__)


class SQLiteConnector:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute_query(self, query: str, params=None) -> QueryResult:
        self._validate_readonly_query(query)

        start_time = time.time()
        # Open in read-only URI mode
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            cursor = conn.cursor()
            if params:
                # Convert dict params to positional (sql.js uses ? markers)
                # Backend uses %(key)s style from PostgreSQL; convert to ?
                cursor.execute(query, params) if isinstance(params, (list, tuple)) else cursor.execute(query, list(params.values()))
            else:
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
        # Reuse the same validation logic as BaseConnector
        query_upper = query.strip().upper()

        if len(query) > 10_000:
            raise ValueError("Query exceeds maximum allowed length of 10,000 characters.")

        lines = [line.split('--')[0] for line in query_upper.split('\n')]
        query_clean = ' '.join(lines)
        query_clean = re.sub(r'/\*.*?\*/', ' ', query_clean, flags=re.DOTALL)
        query_clean = ' '.join(query_clean.split())

        if ';' in query_clean.rstrip(';'):
            raise ValueError("Multiple statements not allowed. Only single SELECT queries permitted.")

        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
            'COPY', 'LOAD', 'SET', 'CALL', 'RENAME',
            'INTO', 'EXPLAIN', 'VACUUM', 'REINDEX', 'CLUSTER',
            'COMMENT', 'NOTIFY', 'LISTEN', 'UNLISTEN', 'DO',
            'PREPARE', 'DEALLOCATE',
        ]
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', query_clean):
                raise ValueError(f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed.")

        # Block SQLite-specific dangerous functions
        dangerous_sqlite_functions = [
            r'\bload_extension\b', r'\breadfile\b', r'\bwritefile\b',
        ]
        for pattern in dangerous_sqlite_functions:
            if re.search(pattern, query_clean):
                raise ValueError("Query contains a forbidden SQLite function.")

        if not re.match(r'^(SELECT|WITH)\b', query_clean):
            raise ValueError("Query must start with SELECT or WITH (for CTEs)")

    def close(self):
        pass  # No persistent connection to close

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
