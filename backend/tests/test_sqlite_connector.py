"""Tests for SqliteFileConnector."""

import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.connectors.sqlite import SqliteFileConnector
from backend.connectors.base import QueryResult, TableSchema
from backend.database.base import Base
from backend.models.database_connection import DatabaseConnection
from backend.models.organization import Organization
from backend.models.user import User
import backend.models.user_skill  # noqa: F401


@pytest.fixture
def sample_db():
    """Create a temporary SQLite database with sample data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, score REAL)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice', 9.5)")
    conn.execute("INSERT INTO users VALUES (2, 'Bob', 7.2)")
    conn.execute("INSERT INTO users VALUES (3, 'Charlie', 8.8)")
    conn.commit()
    conn.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def multi_table_db():
    """Create a temporary SQLite database with multiple tables and foreign keys."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE employees ("
        "id INTEGER PRIMARY KEY, "
        "name TEXT, "
        "dept_id INTEGER, "
        "FOREIGN KEY (dept_id) REFERENCES departments(id))"
    )
    conn.execute("INSERT INTO departments VALUES (1, 'Engineering')")
    conn.execute("INSERT INTO departments VALUES (2, 'Sales')")
    conn.execute("INSERT INTO employees VALUES (1, 'Alice', 1)")
    conn.execute("INSERT INTO employees VALUES (2, 'Bob', 2)")
    conn.commit()
    conn.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def db_session():
    """Create an in-memory SQLAlchemy session for testing from_connection."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        Organization.__table__,
        User.__table__,
        DatabaseConnection.__table__,
    ])
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _make_connection(db_session, **kwargs):
    defaults = dict(
        user_id="user-1", name="test-sqlite", db_type="sqlite",
        host="internal", port=0, database="sqlite",
        username="sqlite", _encrypted_password="sqlite",
        dataset_table_name="sqlite/user1/test.sqlite",
    )
    defaults.update(kwargs)
    conn = DatabaseConnection(**defaults)
    db_session.add(conn)
    db_session.commit()
    return conn


class TestExecuteQuery:

    def test_execute_readonly_select(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        result = connector.execute_query("SELECT * FROM users ORDER BY id")

        assert isinstance(result, QueryResult)
        assert result.columns == ["id", "name", "score"]
        assert result.row_count == 3
        assert result.rows[0] == (1, "Alice", 9.5)
        assert result.rows[2] == (3, "Charlie", 8.8)
        assert result.truncated is False

    def test_reject_insert_query(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        with pytest.raises(ValueError, match="INSERT"):
            connector.execute_query("INSERT INTO users VALUES (4, 'Dave', 6.0)")

    def test_reject_drop_query(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        with pytest.raises(ValueError, match="DROP"):
            connector.execute_query("DROP TABLE users")

    def test_reject_load_extension(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        with pytest.raises(ValueError, match="forbidden SQLite function"):
            connector.execute_query("SELECT load_extension('evil.so')")

    def test_ilike_rewritten_to_like(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        result = connector.execute_query("SELECT * FROM users WHERE name ILIKE 'alice'")
        # SQLite LIKE is case-insensitive for ASCII by default
        assert result.row_count >= 0  # Just verify it doesn't error

    @patch("backend.config.settings")
    def test_max_rows_truncation(self, mock_settings, sample_db):
        mock_settings.max_query_rows = 2
        connector = SqliteFileConnector(sample_db)
        result = connector.execute_query("SELECT * FROM users ORDER BY id")

        assert result.row_count == 2
        assert result.truncated is True
        assert len(result.rows) == 2


class TestSchemaDiscovery:

    def test_get_schemas_returns_main(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        assert connector.get_schemas() == ["main"]

    def test_get_tables(self, multi_table_db):
        connector = SqliteFileConnector(multi_table_db)
        tables = connector.get_tables()
        assert sorted(tables) == ["departments", "employees"]

    def test_get_table_schema(self, sample_db):
        connector = SqliteFileConnector(sample_db)
        schema = connector.get_table_schema("users")

        assert isinstance(schema, TableSchema)
        assert schema.table_name == "users"
        assert schema.row_count == 3

        col_names = [c["name"] for c in schema.columns]
        assert col_names == ["id", "name", "score"]

        # Check type mapping
        col_types = {c["name"]: c["type"] for c in schema.columns}
        assert col_types["id"] == "BIGINT"       # INTEGER -> BIGINT
        assert col_types["name"] == "TEXT"        # TEXT -> TEXT
        assert col_types["score"] == "DOUBLE PRECISION"  # REAL -> DOUBLE PRECISION

        # Check primary key
        pk_cols = [c["name"] for c in schema.columns if c["primary_key"]]
        assert pk_cols == ["id"]

    def test_get_foreign_keys(self, multi_table_db):
        connector = SqliteFileConnector(multi_table_db)
        fks = connector.get_foreign_keys("employees")

        assert len(fks) == 1
        assert fks[0]["from_column"] == "dept_id"
        assert fks[0]["to_table"] == "departments"
        assert fks[0]["to_column"] == "id"


class TestFromConnection:

    @patch("backend.services.object_storage.download_bytes")
    @patch("backend.config.settings")
    def test_from_connection_caches_file(self, mock_settings, mock_download, sample_db, tmp_path):
        mock_settings.dataset_cache_dir = str(tmp_path)

        with open(sample_db, "rb") as f:
            file_bytes = f.read()
        mock_download.return_value = file_bytes

        conn = MagicMock()
        conn.id = 999
        conn.dataset_table_name = "sqlite/user1/test.sqlite"

        # First call — downloads
        connector1 = SqliteFileConnector.from_connection(conn)
        assert mock_download.call_count == 1

        # Second call — uses cache
        connector2 = SqliteFileConnector.from_connection(conn)
        assert mock_download.call_count == 1  # Not called again

        # Both should work
        assert os.path.exists(connector1.db_path)
        assert connector1.db_path == connector2.db_path

    @patch("backend.services.object_storage.download_bytes", return_value=None)
    @patch("backend.config.settings")
    def test_from_connection_marks_unhealthy_on_missing_file(self, mock_settings, mock_download, db_session, tmp_path):
        mock_settings.dataset_cache_dir = str(tmp_path)
        conn = _make_connection(db_session)

        with pytest.raises(FileNotFoundError):
            SqliteFileConnector.from_connection(conn, db_session=db_session)

        db_session.refresh(conn)
        assert conn.health_status == "unhealthy"
        assert conn.health_checked_at is not None
