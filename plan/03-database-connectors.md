# Phase 03: Database Connectors

## Objective

Build database connector system with factory pattern supporting PostgreSQL and MySQL, read-only enforcement, schema discovery, and connection testing.

## Prerequisites

- Phase 01: App Database (DatabaseConnection model)
- Phase 02: Authentication (to protect API endpoints)

## Files to Create

### Connector System
- `backend/connectors/__init__.py` - Export connector classes
- `backend/connectors/base.py` - BaseConnector abstract class
- `backend/connectors/factory.py` - Connector factory pattern
- `backend/connectors/postgres.py` - PostgresConnector implementation
- `backend/connectors/mysql.py` - MySQLConnector implementation

### Schema Discovery Service
- `backend/services/schema_discovery.py` - Auto-discover and cache schemas as JSON

### API & Schemas
- `backend/api/connections.py` - CRUD endpoints for database connections
- `backend/schemas/connection.py` - Pydantic schemas for connections

### Infrastructure
- `data/schemas/` - Directory for cached schema JSON files

### Tests
- `backend/tests/test_connectors.py` - Unit tests for connectors
- `backend/tests/test_connections_api.py` - Integration tests for API
- `backend/tests/test_schema_discovery.py` - Tests for schema discovery

## Files to Modify

- `backend/api/routes.py` - Register connections routes
- `backend/models/database_connection.py` - Add schema_json_path, schema_generated_at
- `backend/config.py` - Add schemas_dir setting
- `requirements.txt` - Add psycopg2-binary, PyMySQL, cryptography
- `docker-compose.yml` - Add volume mount for data/schemas/

## Implementation Details

### 1. BaseConnector (backend/connectors/base.py)

```python
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

    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self._connection = None

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

    @abstractmethod
    def _db_type_name(self) -> str:
        """
        Human-readable database type name for error messages.

        Returns:
            Database type (e.g., "PostgreSQL", "MySQL")
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
        row_count = cursor.fetchone()['count'] if isinstance(cursor.fetchone(), dict) else cursor.fetchone()[0]

        # Re-fetch since we consumed the result
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

    def _validate_readonly_query(self, query: str) -> None:
        """
        Validate that query is read-only (SELECT only).

        Raises:
            ValueError: If query contains non-SELECT statements
        """
        query_upper = query.strip().upper()

        # Remove comments
        lines = [line.split('--')[0] for line in query_upper.split('\n')]
        query_clean = ' '.join(lines).strip()

        # Check for dangerous keywords
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
            'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
        ]

        for keyword in dangerous_keywords:
            if keyword in query_clean:
                raise ValueError(f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed.")

        # Ensure query starts with SELECT
        if not query_clean.startswith('SELECT') and not query_clean.startswith('WITH'):
            raise ValueError("Query must start with SELECT or WITH (for CTEs)")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
```

### 2. PostgresConnector (backend/connectors/postgres.py)

```python
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
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'user': self.username,
            'password': self.password
        }

    def _quote_identifier(self, name: str) -> str:
        """Quote identifier with double quotes for PostgreSQL."""
        return f'"{name}"'

    def _db_type_name(self) -> str:
        """Return database type name."""
        return "PostgreSQL"

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
```

### 3. MySQLConnector (backend/connectors/mysql.py)

```python
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
```

### Template Method Pattern Benefits

**Code Reduction:**
- BaseConnector: ~9 concrete methods + 6 abstract + 4 hooks
- PostgresConnector: ~45 lines (9 methods, mostly one-liners)
- MySQLConnector: ~35 lines (8 methods, mostly one-liners)

**Previous approach (without template method):**
- PostgresConnector: ~110 lines, 8 full methods
- MySQLConnector: ~115 lines, 8 full methods
- ~70% code duplication between connectors

**Adding a new connector (e.g., MSSQL):**

```python
class MSSQLConnector(BaseConnector):
    """SQL Server connector - only ~50 lines needed."""

    def _create_connection(self, **kwargs):
        return pyodbc.connect(**kwargs)

    def _is_connection_alive(self, conn) -> bool:
        # Check connection status
        pass

    def _get_cursor(self, conn, dict_mode: bool = False):
        # Return cursor
        pass

    def _get_connect_kwargs(self) -> dict:
        # Map to pyodbc kwargs
        pass

    def _quote_identifier(self, name: str) -> str:
        return f'[{name}]'  # MSSQL uses brackets

    def _db_type_name(self) -> str:
        return "SQL Server"

    def _param_marker(self) -> str:
        return "?"  # MSSQL uses ? placeholders

    def _system_schemas(self) -> set:
        return {"information_schema", "sys", "INFORMATION_SCHEMA"}
```

Only 6 required methods + 2 hooks = ~50 lines total vs. ~115 lines with copy-paste approach.

### 4. Schema Discovery Service (backend/services/schema_discovery.py)

```python
import json
import os
from typing import Dict, Any, List
from datetime import datetime
from backend.connectors.base import BaseConnector
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

def discover_schema(connector: BaseConnector) -> Dict[str, Any]:
    """
    Auto-discover full database schema.

    Args:
        connector: Database connector instance

    Returns:
        Dict with schemas, tables, columns, relationships, row counts
    """
    logger.info("Starting schema discovery")

    schema_data = {
        "schemas": {},
        "table_names": [],
        "relationships": []
    }

    # Get all schemas/databases
    schemas = connector.get_schemas()

    for schema_name in schemas:
        schema_data["schemas"][schema_name] = {"tables": {}}

        # Get all tables in schema
        tables = connector.get_tables(schema_name)

        for table_name in tables:
            schema_data["table_names"].append(table_name)

            # Get table schema
            table_schema = connector.get_table_schema(table_name, schema_name)

            # Get foreign keys
            foreign_keys = connector.get_foreign_keys(table_name, schema_name)

            # Store table info
            schema_data["schemas"][schema_name]["tables"][table_name] = {
                "row_count": table_schema.row_count,
                "columns": table_schema.columns
            }

            # Store relationships
            for fk in foreign_keys:
                schema_data["relationships"].append({
                    "from": f"{table_name}.{fk['from_column']}",
                    "to": f"{fk['to_table']}.{fk['to_column']}"
                })

    logger.info(f"Schema discovery completed: {len(schema_data['table_names'])} tables")

    return schema_data


def generate_schema_json(
    connection_id: int,
    connection_name: str,
    db_type: str,
    schema_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate structured schema JSON format.

    Returns:
        Complete schema JSON with metadata
    """
    return {
        "connection_id": connection_id,
        "connection_name": connection_name,
        "db_type": db_type,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schemas": schema_data["schemas"],
        "table_names": schema_data["table_names"],
        "relationships": schema_data["relationships"]
    }


def save_schema_file(connection_id: int, schema_json: Dict[str, Any]) -> str:
    """
    Save schema JSON to file.

    Args:
        connection_id: Database connection ID
        schema_json: Complete schema JSON

    Returns:
        Path to saved JSON file
    """
    # Ensure schemas directory exists
    schemas_dir = settings.schemas_dir
    os.makedirs(schemas_dir, exist_ok=True)

    # Generate file path
    file_path = os.path.join(schemas_dir, f"{connection_id}_schema.json")

    # Write JSON file
    with open(file_path, 'w') as f:
        json.dump(schema_json, f, indent=2)

    logger.info(f"Schema saved to {file_path}")

    return file_path


def load_schema_file(connection_id: int) -> Dict[str, Any]:
    """
    Load schema JSON from file.

    Args:
        connection_id: Database connection ID

    Returns:
        Schema JSON dict

    Raises:
        FileNotFoundError: If schema file doesn't exist
    """
    file_path = os.path.join(settings.schemas_dir, f"{connection_id}_schema.json")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Schema file not found: {file_path}")

    with open(file_path, 'r') as f:
        return json.load(f)


def refresh_schema(connection_id: int, connector: BaseConnector, connection_name: str, db_type: str) -> str:
    """
    Re-discover and regenerate schema JSON.

    Args:
        connection_id: Database connection ID
        connector: Database connector instance
        connection_name: Connection name
        db_type: Database type

    Returns:
        Path to regenerated schema file
    """
    logger.info(f"Refreshing schema for connection {connection_id}")

    # Discover schema
    schema_data = discover_schema(connector)

    # Generate JSON
    schema_json = generate_schema_json(connection_id, connection_name, db_type, schema_data)

    # Save to file
    file_path = save_schema_file(connection_id, schema_json)

    return file_path


def delete_schema_file(connection_id: int) -> bool:
    """
    Delete schema JSON file.

    Args:
        connection_id: Database connection ID

    Returns:
        True if deleted, False if file didn't exist
    """
    file_path = os.path.join(settings.schemas_dir, f"{connection_id}_schema.json")

    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted schema file: {file_path}")
        return True

    return False
```

### 5. Connector Factory (backend/connectors/factory.py)

```python
from typing import Type
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector
from backend.models.database_connection import DatabaseType

_CONNECTORS: dict[DatabaseType, Type[BaseConnector]] = {
    DatabaseType.POSTGRES: PostgresConnector,
    DatabaseType.MYSQL: MySQLConnector,
}

def get_connector(
    db_type: DatabaseType,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str
) -> BaseConnector:
    """
    Factory function to create database connector.

    Args:
        db_type: Type of database (postgres, mysql)
        host: Database host
        port: Database port
        database: Database name
        username: Database username
        password: Database password

    Returns:
        Instance of appropriate connector class

    Raises:
        ValueError: If database type not supported
    """
    connector_class = _CONNECTORS.get(db_type)

    if connector_class is None:
        raise ValueError(f"Unsupported database type: {db_type}")

    return connector_class(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password
    )
```

### 6. Connection Schemas (backend/schemas/connection.py)

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from backend.models.database_connection import DatabaseType
from datetime import datetime

class ConnectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    db_type: DatabaseType
    host: str
    port: int = Field(..., gt=0, lt=65536)
    database: str
    username: str
    password: str

class ConnectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    host: Optional[str] = None
    port: Optional[int] = Field(None, gt=0, lt=65536)
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class ConnectionResponse(BaseModel):
    id: int
    user_id: str
    name: str
    db_type: DatabaseType
    host: str
    port: int
    database: str
    username: str
    is_active: bool
    schema_json_path: Optional[str]
    schema_generated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ConnectionTestResponse(BaseModel):
    success: bool
    message: str

class SchemaRefreshResponse(BaseModel):
    success: bool
    message: str
    schema_generated_at: datetime
```

### 7. Connections API (backend/api/connections.py)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.connection import (
    ConnectionCreate, ConnectionUpdate, ConnectionResponse,
    ConnectionTestResponse, SchemaRefreshResponse
)
from backend.connectors.factory import get_connector
from backend.services.schema_discovery import (
    discover_schema, generate_schema_json, save_schema_file,
    refresh_schema, delete_schema_file
)
from datetime import datetime

router = APIRouter(prefix="/connections", tags=["connections"])

@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    request: ConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new database connection with automatic schema discovery.

    Flow:
    1. Test connection (5s timeout)
    2. Save connection to database
    3. Auto-discover full schema
    4. Save schema as JSON to data/schemas/{id}_schema.json
    5. Update connection with schema path and timestamp
    """
    # Test connection before saving
    try:
        connector = get_connector(
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password
        )
        connector.test_connection()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test failed: {str(e)}"
        )

    # Create connection (without schema info yet)
    connection = DatabaseConnection(
        user_id=current_user.id,
        **request.model_dump()
    )

    db.add(connection)
    db.commit()
    db.refresh(connection)

    # Auto-discover schema
    try:
        schema_data = discover_schema(connector)
        schema_json = generate_schema_json(
            connection.id,
            connection.name,
            connection.db_type.value,
            schema_data
        )
        schema_path = save_schema_file(connection.id, schema_json)

        # Update connection with schema info
        connection.schema_json_path = schema_path
        connection.schema_generated_at = datetime.utcnow()
        db.commit()
        db.refresh(connection)

    except Exception as e:
        # Log error but don't fail connection creation
        # Schema can be generated later via refresh endpoint
        import logging
        logging.error(f"Schema discovery failed: {str(e)}")

    finally:
        connector.close()

    return connection

@router.get("", response_model=List[ConnectionResponse])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all database connections for current user."""
    connections = db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == current_user.id
    ).all()

    return connections

@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific database connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    return connection

@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: int,
    request: ConnectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a database connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Update fields
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(connection, field, value)

    db.commit()
    db.refresh(connection)

    return connection

@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a database connection and its cached schema."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Delete schema JSON file
    delete_schema_file(connection_id)

    # Delete connection from database
    db.delete(connection)
    db.commit()

@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a database connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        connector = get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        )
        connector.test_connection()
        connector.close()

        return ConnectionTestResponse(success=True, message="Connection successful")
    except Exception as e:
        return ConnectionTestResponse(success=False, message=str(e))

@router.post("/{connection_id}/refresh-schema", response_model=SchemaRefreshResponse)
async def refresh_connection_schema(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh cached schema for a database connection.

    Re-discovers full schema and regenerates JSON file.
    Useful when database structure changes.
    """
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        with get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        ) as connector:
            schema_path = refresh_schema(
                connection.id,
                connector,
                connection.name,
                connection.db_type.value
            )

            # Update connection timestamp
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            db.commit()
            db.refresh(connection)

            return SchemaRefreshResponse(
                success=True,
                message="Schema refreshed successfully",
                schema_generated_at=connection.schema_generated_at
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema refresh failed: {str(e)}"
        )
```

### 8. Configuration (backend/config.py)

Add schema storage directory setting:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Schema storage
    schemas_dir: str = "data/schemas"
```

### 9. Register Routes (backend/api/routes.py)

```python
from backend.api import connections  # Add import

# In create_api_router():
api_router.include_router(connections.router)
```

### 10. Database Model Updates (backend/models/database_connection.py)

Add schema caching fields:

```python
from sqlalchemy import Column, String, DateTime

class DatabaseConnection(Base):
    # ... existing fields ...

    schema_json_path = Column(String, nullable=True)
    schema_generated_at = Column(DateTime(timezone=True), nullable=True)
```

### 11. Docker Configuration (docker-compose.yml)

Add volume mount for schema storage:

```yaml
services:
  backend:
    volumes:
      - ./data/schemas:/app/data/schemas
```

### 12. Update Requirements

```txt
psycopg2-binary==2.9.9
PyMySQL==1.1.0
cryptography==41.0.7
```

## Testing & Verification

### Manual Testing Steps

1. **Create connection**: POST /api/connections
   - Verify connection test succeeds
   - Verify schema JSON file created at data/schemas/{id}_schema.json
   - Verify response includes schema_json_path and schema_generated_at

2. **Inspect schema JSON**:
   ```bash
   cat data/schemas/1_schema.json
   # Should contain: connection_id, connection_name, db_type, generated_at,
   # schemas, table_names, relationships
   ```

3. **Refresh schema**: POST /api/connections/{id}/refresh-schema
   - Verify schema_generated_at timestamp updates
   - Verify JSON file regenerated

4. **Delete connection**: DELETE /api/connections/{id}
   - Verify connection removed from database
   - Verify schema JSON file deleted from data/schemas/

### Unit Tests

```python
# backend/tests/test_schema_discovery.py
def test_discover_schema():
    """Test schema discovery returns all tables and columns."""
    pass

def test_generate_schema_json():
    """Test schema JSON format is correct."""
    pass

def test_save_and_load_schema():
    """Test schema persistence to file."""
    pass
```

## MCP Browser Testing

Test connection CRUD flow:

```python
# Navigate to Swagger UI
navigate_page(url="http://localhost:8000/docs")

# Authorize with JWT token first (from Phase 02)
# Test POST /api/connections - verify schema auto-generated
# Test POST /api/connections/{id}/refresh-schema
# Verify schema JSON files exist in file system
```

## Code Review Checklist

### Template Method Pattern
- [ ] BaseConnector implements all common template methods (test_connection, get_schemas, get_tables, etc.)
- [ ] Subclasses only implement abstract primitives and override hooks as needed
- [ ] No code duplication between PostgresConnector and MySQLConnector
- [ ] New connectors can be added with ~50 lines by implementing 6 abstract methods

### Security & Validation
- [ ] Read-only query validation prevents INSERT/UPDATE/DELETE
- [ ] Connection strings validated before saving
- [ ] Passwords stored securely (consider encryption)
- [ ] Context manager used for connector lifecycle
- [ ] SQL injection prevented via parameterized queries
- [ ] Error messages don't expose credentials
- [ ] Timeout on connection attempts (5 seconds)
- [ ] All endpoints require authentication

### Functionality
- [ ] Connection pooling considered for production
- [ ] Schema discovery runs automatically on connection creation
- [ ] Schema JSON files saved to data/schemas/ directory
- [ ] Schema files deleted when connection is deleted
- [ ] Foreign key relationships captured in schema
- [ ] data/schemas/ directory created on startup if missing
- [ ] Schema refresh endpoint works correctly

## Done Criteria

### Template Method Pattern
1. BaseConnector uses template method pattern with 9 concrete methods
2. PostgresConnector is ~45 lines with 9 minimal methods
3. MySQLConnector is ~35 lines with 8 minimal methods
4. No code duplication between connectors (verify with diff/comparison)
5. Adding new connector only requires implementing 6 abstract methods + optional hooks

### Core Functionality
6. Can create, read, update, delete database connections
7. Can test connection before saving (5 second timeout)
8. PostgreSQL connector works (schema discovery, query execution, foreign keys)
9. MySQL connector works (schema discovery, query execution, foreign keys)
10. Read-only validation blocks dangerous queries (INSERT/UPDATE/DELETE/DROP/etc.)

### Schema Discovery
11. Schema JSON generated automatically on connection creation
12. Schema JSON saved to data/schemas/{id}_schema.json
13. Schema JSON contains: tables, columns, types, FKs, row counts, relationships
14. Can refresh schema via POST /connections/{id}/refresh-schema
15. Schema files deleted when connection deleted

### Security & Testing
16. All endpoints require JWT authentication
17. Unit tests pass
18. Integration tests pass
19. Swagger UI shows all connection endpoints

## Rollback Plan

If this phase fails:
1. Remove backend/connectors/ directory
2. Remove backend/schemas/connection.py
3. Remove connections routes from backend/api/routes.py
4. Remove connector dependencies from requirements.txt
