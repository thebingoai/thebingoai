"""Schema persistence now writes to database_connections.schema_json (JSONB),
not DO Spaces. These tests cover the save/load/delete surface + the legacy
DO Spaces key rejection path.
"""
from unittest.mock import MagicMock, patch

import pytest


def test_schema_key_for_returns_db_marker():
    from backend.services.schema_discovery import schema_key_for
    conn = MagicMock(id=42)
    assert schema_key_for(conn) == "db:42"


@patch("backend.database.session.SessionLocal")
def test_save_schema_file_writes_to_db(mock_session_factory):
    from backend.services.schema_discovery import save_schema_file

    conn = MagicMock(id=17)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = conn
    mock_session_factory.return_value = db

    payload = {"table_names": ["t1", "t2"], "schemas": {"public": {}}}
    key = save_schema_file("db:17", payload)

    assert key == "db:17"
    assert conn.schema_json == payload
    assert conn.schema_json_path == "db:17"
    db.commit.assert_called_once()


@patch("backend.database.session.SessionLocal")
def test_save_schema_file_unknown_connection_raises(mock_session_factory):
    from backend.services.schema_discovery import save_schema_file

    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    mock_session_factory.return_value = db

    with pytest.raises(ValueError, match="No connection with id 999"):
        save_schema_file("db:999", {"table_names": []})


@patch("backend.database.session.SessionLocal")
def test_load_schema_file_int_id_reads_db(mock_session_factory):
    from backend.services.schema_discovery import load_schema_file

    payload = {"table_names": ["a", "b", "c"]}
    conn = MagicMock(schema_json=payload)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = conn
    mock_session_factory.return_value = db

    assert load_schema_file(7) == payload


@patch("backend.database.session.SessionLocal")
def test_load_schema_file_db_key_reads_db(mock_session_factory):
    from backend.services.schema_discovery import load_schema_file

    payload = {"table_names": ["x"]}
    conn = MagicMock(schema_json=payload)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = conn
    mock_session_factory.return_value = db

    assert load_schema_file("db:7") == payload


def test_load_schema_file_legacy_do_key_raises():
    """Legacy DO Spaces keys (anything not starting with 'db:') must raise
    FileNotFoundError so callers know the old path is dead and a refresh
    is required."""
    from backend.services.schema_discovery import load_schema_file

    with pytest.raises(FileNotFoundError, match="legacy DO Spaces key"):
        load_schema_file("schemas/some/legacy/key.json")


@patch("backend.database.session.SessionLocal")
def test_load_schema_file_missing_data_raises(mock_session_factory):
    from backend.services.schema_discovery import load_schema_file

    conn = MagicMock(schema_json=None)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = conn
    mock_session_factory.return_value = db

    with pytest.raises(FileNotFoundError, match="No schema for connection"):
        load_schema_file(7)


@patch("backend.database.session.SessionLocal")
def test_delete_schema_file_clears_columns(mock_session_factory):
    from backend.services.schema_discovery import delete_schema_file

    conn = MagicMock(schema_json={"x": 1}, schema_json_path="db:7")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = conn
    mock_session_factory.return_value = db

    assert delete_schema_file("db:7") is True
    assert conn.schema_json is None
    assert conn.schema_json_path is None
    db.commit.assert_called_once()


def test_delete_schema_file_noop_on_none():
    from backend.services.schema_discovery import delete_schema_file
    assert delete_schema_file(None) is False


def test_delete_schema_file_noop_on_legacy_key():
    """Legacy DO Spaces keys (no db: prefix) are a no-op since the DO
    backend is gone."""
    from backend.services.schema_discovery import delete_schema_file
    assert delete_schema_file("schemas/legacy.json") is False
