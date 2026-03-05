from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import time


@dataclass
class TableSchema:
    """Represents a database table schema."""
    table_name: str
    columns: List[Dict[str, Any]]  # [{name, type, nullable, primary_key}, ...]
    row_count: Optional[int] = None


@dataclass
class QueryResult:
    """Represents a query execution result."""
    columns: List[str]
    rows: List[tuple]
    row_count: int
    execution_time_ms: float


class BaseConnector(ABC):
    """
    Template method base class for database connectors using Template Method pattern.

    Provides concrete implementations of common functionality while requiring
    subclasses to implement database-specific primitives.

    **To add a new database connector:**
    1. Extend BaseConnector
    2. Implement 6 abstract methods (_create_connection, _is_connection_alive,
       _get_cursor, _get_connect_kwargs, _quote_identifier, _db_type_name)
    3. Optionally override 4 hooks (_default_schema, _system_schemas,
       _param_marker, _foreign_key_query)
    4. Register in factory.py

    See PostgresConnector and MySQLConnector for examples.
    """

    def __init__(self, host: str, port: int, database: str, username: str, password: str,
                 ssl_enabled: bool = False, ssl_ca_cert: Optional[str] = None):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self.ssl_enabled = ssl_enabled
        self.ssl_ca_cert = ssl_ca_cert  # decrypted PEM content
        self._connection = None
        self._temp_ca_file = None

    # ============================================================
    # Abstract Primitives (MUST implement in subclasses)
    # ============================================================

    @abstractmethod
    def _create_connection(self, **kwargs):
        """
        Create a driver-specific database connection.

        Args:
            **kwargs: Connection parameters from _get_connect_kwargs()

        Returns:
            Database connection object
        """
        pass

    @abstractmethod
    def _is_connection_alive(self, conn) -> bool:
        """
        Check if a connection is still alive/open.

        Args:
            conn: Database connection to check

        Returns:
            True if connection is alive, False otherwise
        """
        pass

    @abstractmethod
    def _get_cursor(self, conn, dict_mode: bool = False):
        """
        Get a cursor from the connection.

        Args:
            conn: Database connection
            dict_mode: If True, return dict-like cursor for internal schema queries

        Returns:
            Cursor object (tuple cursor for execute_query, dict cursor for schema queries)
        """
        pass

    @abstractmethod
    def _get_connect_kwargs(self) -> dict:
        """
        Map connector properties to driver-specific connection kwargs.

        Returns:
            Dict of kwargs for _create_connection()

        Example:
            {'host': self.host, 'port': self.port, 'database': self.database, ...}
        """
        pass

    @abstractmethod
    def _quote_identifier(self, name: str) -> str:
        """
        Quote a table/column identifier for safe SQL construction.

        Args:
            name: Identifier to quote

        Returns:
            Quoted identifier (e.g., "name" for PostgreSQL, `name` for MySQL)
        """
        pass

    @classmethod
    @abstractmethod
    def _db_type_name(cls) -> str:
        """
        Human-readable database type name for error messages.

        Returns:
            Database type (e.g., "PostgreSQL", "MySQL")
        """
        pass

    @classmethod
    @abstractmethod
    def _default_port(cls) -> int:
        """
        Default port number for this database type.

        Returns:
            Default port (e.g., 5432 for PostgreSQL, 3306 for MySQL)
        """
        pass

    @classmethod
    @abstractmethod
    def _description(cls) -> str:
        """
        Short human-readable description for UI display.

        Returns:
            Description string (e.g., "Open-source relational database")
        """
        pass

    @classmethod
    @abstractmethod
    def _badge_variant(cls) -> str:
        """
        Badge variant for UI display.

        Returns:
            Variant string (e.g., "info", "warning")
        """
        pass

    # ============================================================
    # Overridable Hooks (have sensible defaults)
    # ============================================================

    def _default_schema(self) -> str:
        """
        Default schema to use when none specified.

        Returns:
            Schema name (default: "public")
        """
        return "public"

    def _system_schemas(self) -> set:
        """
        Set of system schemas to exclude from schema lists.

        Returns:
            Set of schema names to filter out (default: {"information_schema"})
        """
        return {"information_schema"}

    def _param_marker(self) -> str:
        """
        Parameter placeholder style for queries.

        Returns:
            Placeholder string (default: "%s" for psycopg2/PyMySQL)
        """
        return "%s"

    def _foreign_key_query(self, schema: str, table: str) -> tuple:
        """
        Generate SQL query to fetch foreign keys for a table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Tuple of (sql_query, params)

        Default uses MySQL-style information_schema. PostgreSQL overrides this.
        """
        marker = self._param_marker()
        return (f"""
            SELECT
                COLUMN_NAME as from_column,
                REFERENCED_TABLE_NAME as to_table,
                REFERENCED_COLUMN_NAME as to_column
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = {marker} AND TABLE_NAME = {marker}
              AND REFERENCED_TABLE_NAME IS NOT NULL
        """, (schema, table))

    # ============================================================
    # Concrete Template Methods (shared by all connectors)
    # ============================================================

    def _get_ca_cert_path(self) -> Optional[str]:
        """
        Write CA cert to temp file, return path. Both psycopg2 and PyMySQL need file paths.

        Returns:
            Path to temporary CA cert file or None if no cert
        """
        if not self.ssl_ca_cert:
            return None
        import tempfile
        self._temp_ca_file = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
        self._temp_ca_file.write(self.ssl_ca_cert)
        self._temp_ca_file.flush()
        self._temp_ca_file.close()
        return self._temp_ca_file.name

    def _cleanup_temp_files(self):
        """Clean up temporary CA certificate file."""
        if self._temp_ca_file:
            import os
            try:
                os.unlink(self._temp_ca_file.name)
            except OSError:
                pass
            self._temp_ca_file = None

    def test_connection(self) -> bool:
        """
        Test if connection is successful.

        Returns:
            True if connection succeeds

        Raises:
            ConnectionError: If connection fails
        """
        try:
            kwargs = self._get_connect_kwargs()
            kwargs['connect_timeout'] = 5  # 5 second timeout
            conn = self._create_connection(**kwargs)

            # Close connection immediately
            if hasattr(conn, 'close'):
                conn.close()

            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self._db_type_name()}: {str(e)}")
        finally:
            self._cleanup_temp_files()

    def _get_connection(self):
        """
        Get or create lazy database connection.

        Returns:
            Database connection object
        """
        if self._connection is None or not self._is_connection_alive(self._connection):
            kwargs = self._get_connect_kwargs()
            self._connection = self._create_connection(**kwargs)
        return self._connection

    def get_schemas(self) -> List[str]:
        """
        Get list of schemas/databases (excluding system schemas).

        Returns:
            List of schema names
        """
        conn = self._get_connection()
        cursor = self._get_cursor(conn, dict_mode=True)

        cursor.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            ORDER BY schema_name
        """)

        all_schemas = [row['schema_name'] if isinstance(row, dict) else row[0]
                       for row in cursor.fetchall()]

        # Filter out system schemas
        schemas = [s for s in all_schemas if s not in self._system_schemas()]

        cursor.close()
        return schemas

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        """
        Get list of tables in a schema.

        Args:
            schema: Schema name (uses default if None)

        Returns:
            List of table names
        """
        conn = self._get_connection()
        cursor = self._get_cursor(conn, dict_mode=True)

        if schema is None:
            schema = self._default_schema()

        marker = self._param_marker()
        cursor.execute(f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = {marker} AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """, (schema,))

        tables = [row['table_name'] if isinstance(row, dict) else row[0]
                  for row in cursor.fetchall()]

        cursor.close()
        return tables

    def get_table_schema(self, table_name: str, schema: Optional[str] = None) -> TableSchema:
        """
        Get detailed schema for a table including columns and row count.

        Args:
            table_name: Table name
            schema: Schema name (uses default if None)

        Returns:
            TableSchema with columns and row count
        """
        conn = self._get_connection()
        cursor = self._get_cursor(conn, dict_mode=True)

        if schema is None:
            schema = self._default_schema()

        marker = self._param_marker()

        # Get columns
        cursor.execute(f"""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = {marker} AND table_name = {marker}
            ORDER BY ordinal_position
        """, (schema, table_name))

        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row['column_name'] if isinstance(row, dict) else row[0],
                'type': row['data_type'] if isinstance(row, dict) else row[1],
                'nullable': (row['is_nullable'] if isinstance(row, dict) else row[2]) == 'YES',
                'default': row['column_default'] if isinstance(row, dict) else row[3]
            })

        # Get primary keys
        cursor.execute(f"""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = {marker} AND table_name = {marker}
            AND constraint_name IN (
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_schema = {marker} AND table_name = {marker}
                AND constraint_type = 'PRIMARY KEY'
            )
        """, (schema, table_name, schema, table_name))

        primary_keys = {(row['column_name'] if isinstance(row, dict) else row[0])
                       for row in cursor.fetchall()}

        # Mark primary keys
        for col in columns:
            col['primary_key'] = col['name'] in primary_keys

        # Get row count
        quoted_schema = self._quote_identifier(schema)
        quoted_table = self._quote_identifier(table_name)
        cursor.execute(f'SELECT COUNT(*) as count FROM {quoted_schema}.{quoted_table}')
        result = cursor.fetchone()
        row_count = result['count'] if isinstance(result, dict) else result[0]

        cursor.close()

        return TableSchema(
            table_name=table_name,
            columns=columns,
            row_count=row_count
        )

    def get_foreign_keys(self, table_name: str, schema: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Get foreign key relationships for a table.

        Args:
            table_name: Table name
            schema: Schema name (uses default if None)

        Returns:
            List of dicts with 'from_column', 'to_table', 'to_column'
        """
        conn = self._get_connection()
        cursor = self._get_cursor(conn, dict_mode=True)

        if schema is None:
            schema = self._default_schema()

        # Get FK query from overridable hook
        sql, params = self._foreign_key_query(schema, table_name)
        cursor.execute(sql, params)

        fks = []
        for row in cursor.fetchall():
            fks.append({
                'from_column': row['from_column'] if isinstance(row, dict) else row[0],
                'to_table': row['to_table'] if isinstance(row, dict) else row[1],
                'to_column': row['to_column'] if isinstance(row, dict) else row[2]
            })

        cursor.close()
        return fks

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> QueryResult:
        """
        Execute a SELECT query (read-only).

        Args:
            query: SQL query string
            params: Optional parameters for parameterized query

        Returns:
            QueryResult with columns and rows

        Raises:
            ValueError: If query is not read-only (not SELECT)
            Exception: If query execution fails
        """
        self._validate_readonly_query(query)

        conn = self._get_connection()
        cursor = self._get_cursor(conn, dict_mode=False)  # Use tuple cursor

        start_time = time.time()

        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            execution_time_ms = (time.time() - start_time) * 1000

            cursor.close()

            return QueryResult(
                columns=columns,
                rows=rows,  # Already tuples from tuple cursor
                row_count=len(rows),
                execution_time_ms=execution_time_ms
            )
        except Exception as e:
            cursor.close()
            raise Exception(f"Query execution failed: {str(e)}")

    def close(self):
        """Close database connection if open."""
        if self._connection and self._is_connection_alive(self._connection):
            self._connection.close()
            self._connection = None
        self._cleanup_temp_files()

    def _validate_readonly_query(self, query: str) -> None:
        """
        Validate that query is read-only (SELECT only).

        Defense-in-depth validation layer. Should be combined with database-level
        read-only enforcement (SET TRANSACTION READ ONLY) for security.

        Raises:
            ValueError: If query contains non-SELECT statements
        """
        import re
        query_upper = query.strip().upper()

        # Remove SQL comments (both -- and /* */ styles)
        # Strip line comments
        lines = [line.split('--')[0] for line in query_upper.split('\n')]
        query_clean = ' '.join(lines)

        # Strip block comments /* ... */
        query_clean = re.sub(r'/\*.*?\*/', ' ', query_clean, flags=re.DOTALL)
        query_clean = ' '.join(query_clean.split())  # Normalize whitespace

        # Block semicolons (prevent multi-statement queries)
        if ';' in query_clean.rstrip(';'):  # Allow trailing semicolon only
            raise ValueError("Multiple statements not allowed. Only single SELECT queries permitted.")

        # Check for dangerous keywords (word boundaries to prevent false positives)
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
            'COPY', 'LOAD', 'SET', 'CALL', 'RENAME',
        ]

        for keyword in dangerous_keywords:
            # Use word boundary regex to match whole words only
            if re.search(rf'\b{keyword}\b', query_clean):
                raise ValueError(f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed.")

        # Ensure query starts with SELECT or WITH (for CTEs)
        if not re.match(r'^(SELECT|WITH)\b', query_clean):
            raise ValueError("Query must start with SELECT or WITH (for CTEs)")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
