"""Tests for SQLite upload route and factory registration."""

import io
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from backend.connectors.factory import get_available_types, get_connector_for_connection
from backend.connectors.sqlite import SqliteFileConnector


def _create_sample_sqlite_bytes(tables=True) -> bytes:
    """Create a valid SQLite database file in memory and return its bytes."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    if tables:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'Alice')")
        conn.execute("INSERT INTO users VALUES (2, 'Bob')")
        conn.commit()
    conn.close()
    with open(tmp.name, "rb") as f:
        data = f.read()
    os.unlink(tmp.name)
    return data


class TestFactoryRegistration:

    def test_sqlite_registered_in_factory(self):
        types = get_available_types()
        sqlite_types = [t for t in types if t["id"] == "sqlite"]
        assert len(sqlite_types) == 1
        t = sqlite_types[0]
        assert t["display_name"] == "SQLite"
        assert t["default_port"] == 0
        assert t["badge_variant"] == "secondary"

    @patch("backend.connectors.sqlite.SqliteFileConnector.from_connection")
    def test_get_connector_for_sqlite_connection(self, mock_from_conn):
        mock_connector = MagicMock(spec=SqliteFileConnector)
        mock_from_conn.return_value = mock_connector

        connection = MagicMock()
        connection.db_type = "sqlite"

        result = get_connector_for_connection(connection)
        mock_from_conn.assert_called_once_with(connection)
        assert result == mock_connector


class TestUploadRoute:

    @pytest.fixture
    def sample_sqlite_bytes(self):
        return _create_sample_sqlite_bytes(tables=True)

    @pytest.fixture
    def empty_sqlite_bytes(self):
        return _create_sample_sqlite_bytes(tables=False)

    @pytest.fixture
    def mock_deps(self):
        """Set up common mocks for the upload endpoint."""
        with patch("backend.api.sqlite_upload.get_current_user") as mock_user, \
             patch("backend.api.sqlite_upload.get_db") as mock_db_dep, \
             patch("backend.services.object_storage.upload_bytes") as mock_upload, \
             patch("backend.services.object_storage.download_bytes") as mock_download, \
             patch("backend.api.sqlite_upload.save_schema_file", return_value="/schemas/1_schema.json"), \
             patch("backend.api.sqlite_upload.generate_schema_json", return_value={"test": True}), \
             patch("backend.api.sqlite_upload.settings") as mock_settings:

            user = MagicMock()
            user.id = "user-1"
            mock_user.return_value = user

            mock_settings.dataset_max_file_size = 100 * 1024 * 1024  # 100MB
            mock_settings.do_spaces_base_path = "test"
            mock_settings.enable_governance = False

            yield {
                "user": user,
                "mock_upload": mock_upload,
                "mock_settings": mock_settings,
            }

    @pytest.mark.asyncio
    async def test_upload_valid_sqlite_file(self, sample_sqlite_bytes, mock_deps):
        from backend.api.sqlite_upload import upload_sqlite

        file = MagicMock()
        file.filename = "mydata.sqlite"
        file.read = AsyncMock(return_value=sample_sqlite_bytes)

        db = MagicMock()
        # Make connection.id available after commit
        def set_id(*args, **kwargs):
            pass
        db.commit = MagicMock(side_effect=set_id)

        connection_holder = {}
        original_add = db.add

        def capture_add(obj):
            if hasattr(obj, "db_type"):
                obj.id = 1
                obj.name = "mydata"
                obj.source_filename = "mydata.sqlite"
                obj.schema_json_path = None
                obj.profiling_status = None
                connection_holder["conn"] = obj

        db.add = MagicMock(side_effect=capture_add)
        db.refresh = MagicMock()

        result = await upload_sqlite(
            file=file,
            name=None,
            current_user=mock_deps["user"],
            db=db,
        )

        assert result["id"] == 1
        assert result["name"] == "mydata"
        assert result["source_filename"] == "mydata.sqlite"
        assert result["table_count"] == 1
        assert len(result["tables"]) == 1
        assert result["tables"][0]["name"] == "users"
        assert result["tables"][0]["row_count"] == 2

    @pytest.mark.asyncio
    async def test_upload_rejects_wrong_extension(self, mock_deps):
        from backend.api.sqlite_upload import upload_sqlite
        from fastapi import HTTPException

        file = MagicMock()
        file.filename = "data.txt"
        file.read = AsyncMock(return_value=b"not sqlite")

        with pytest.raises(HTTPException) as exc_info:
            await upload_sqlite(
                file=file, name=None,
                current_user=mock_deps["user"], db=MagicMock(),
            )
        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_rejects_corrupt_file(self, mock_deps):
        from backend.api.sqlite_upload import upload_sqlite
        from fastapi import HTTPException

        file = MagicMock()
        file.filename = "corrupt.sqlite"
        file.read = AsyncMock(return_value=b"this is not a sqlite database at all")

        with pytest.raises(HTTPException) as exc_info:
            await upload_sqlite(
                file=file, name=None,
                current_user=mock_deps["user"], db=MagicMock(),
            )
        assert exc_info.value.status_code == 422
        assert "not a valid SQLite" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, sample_sqlite_bytes, mock_deps):
        from backend.api.sqlite_upload import upload_sqlite
        from fastapi import HTTPException

        mock_deps["mock_settings"].dataset_max_file_size = 10  # 10 bytes

        file = MagicMock()
        file.filename = "big.sqlite"
        file.read = AsyncMock(return_value=sample_sqlite_bytes)

        with pytest.raises(HTTPException) as exc_info:
            await upload_sqlite(
                file=file, name=None,
                current_user=mock_deps["user"], db=MagicMock(),
            )
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_rejects_empty_database(self, empty_sqlite_bytes, mock_deps):
        from backend.api.sqlite_upload import upload_sqlite
        from fastapi import HTTPException

        file = MagicMock()
        file.filename = "empty.sqlite"
        file.read = AsyncMock(return_value=empty_sqlite_bytes)

        with pytest.raises(HTTPException) as exc_info:
            await upload_sqlite(
                file=file, name=None,
                current_user=mock_deps["user"], db=MagicMock(),
            )
        assert exc_info.value.status_code == 422
        assert "no user tables" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_schema_json_generated_after_upload(self, sample_sqlite_bytes, mock_deps):
        from backend.api.sqlite_upload import upload_sqlite

        file = MagicMock()
        file.filename = "schema_test.sqlite"
        file.read = AsyncMock(return_value=sample_sqlite_bytes)

        db = MagicMock()

        def capture_add(obj):
            if hasattr(obj, "db_type"):
                obj.id = 42
                obj.name = "schema_test"
                obj.source_filename = "schema_test.sqlite"
                obj.schema_json_path = None
                obj.profiling_status = None

        db.add = MagicMock(side_effect=capture_add)
        db.refresh = MagicMock()

        with patch("backend.api.sqlite_upload.save_schema_file", return_value="/schemas/42_schema.json") as mock_save, \
             patch("backend.api.sqlite_upload.generate_schema_json", return_value={"test": True}) as mock_gen:
            result = await upload_sqlite(
                file=file, name=None,
                current_user=mock_deps["user"], db=db,
            )

            mock_gen.assert_called_once()
            mock_save.assert_called_once()
            call_args = mock_gen.call_args
            assert call_args.kwargs["db_type"] == "sqlite" or call_args[1].get("db_type") == "sqlite"
