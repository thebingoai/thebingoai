"""Tests for the database connector factory and registry."""

import pytest
from unittest.mock import MagicMock

from backend.connectors.factory import (
    _CONNECTORS,
    register_connector,
    get_connector,
    get_available_types,
    get_connector_registration,
)
from backend.plugins.base import ConnectorRegistration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class StubConnector:
    """Minimal connector stub for registration tests."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs


COMMON_KWARGS = dict(
    host="localhost",
    port=5432,
    database="testdb",
    username="user",
    password="pass",
)


# ---------------------------------------------------------------------------
# Core registrations
# ---------------------------------------------------------------------------

class TestCoreRegistrations:
    """Verify that built-in connectors are registered at import time."""

    def test_postgres_registered(self):
        """PostgreSQL connector is available in the registry."""
        assert "postgres" in _CONNECTORS

    def test_mysql_registered(self):
        """MySQL connector is available in the registry."""
        assert "mysql" in _CONNECTORS


# ---------------------------------------------------------------------------
# get_connector
# ---------------------------------------------------------------------------

class TestGetConnector:
    """Tests for the get_connector factory function."""

    def test_postgres_returns_instance(self):
        """get_connector('postgres') returns a connector instance."""
        conn = get_connector(db_type="postgres", **COMMON_KWARGS)
        from backend.connectors.postgres import PostgresConnector
        assert isinstance(conn, PostgresConnector)

    def test_mysql_returns_instance(self):
        """get_connector('mysql') returns a connector instance."""
        conn = get_connector(db_type="mysql", **COMMON_KWARGS)
        from backend.connectors.mysql import MySQLConnector
        assert isinstance(conn, MySQLConnector)

    def test_unknown_type_raises_value_error(self):
        """Requesting an unregistered type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported database type"):
            get_connector(db_type="oracle", **COMMON_KWARGS)

    def test_case_insensitive_lookup(self):
        """Type lookup is case-insensitive (e.g. 'Postgres')."""
        conn = get_connector(db_type="Postgres", **COMMON_KWARGS)
        from backend.connectors.postgres import PostgresConnector
        assert isinstance(conn, PostgresConnector)


# ---------------------------------------------------------------------------
# get_available_types
# ---------------------------------------------------------------------------

class TestGetAvailableTypes:
    """Tests for get_available_types."""

    def test_returns_list_of_dicts(self):
        """get_available_types returns a list with at least the two core types."""
        types = get_available_types()
        assert isinstance(types, list)
        assert len(types) >= 2

    def test_dict_has_required_keys(self):
        """Each entry contains id, display_name, description, default_port, badge_variant."""
        types = get_available_types()
        for t in types:
            assert "id" in t
            assert "display_name" in t
            assert "description" in t
            assert "default_port" in t
            assert "badge_variant" in t


# ---------------------------------------------------------------------------
# register_connector / get_connector_registration round-trip
# ---------------------------------------------------------------------------

class TestRegisterConnector:
    """Tests for dynamic connector registration."""

    def test_register_and_retrieve(self):
        """A freshly registered connector is retrievable via get_connector_registration."""
        reg = ConnectorRegistration(
            type_id="_test_stub_",
            display_name="Test Stub",
            description="Unit test connector",
            default_port=9999,
            badge_variant="secondary",
            connector_class=StubConnector,
        )
        register_connector(reg)
        try:
            retrieved = get_connector_registration("_test_stub_")
            assert retrieved is not None
            assert retrieved.type_id == "_test_stub_"
            assert retrieved.connector_class is StubConnector
        finally:
            # Cleanup to avoid polluting other tests
            _CONNECTORS.pop("_test_stub_", None)

    def test_get_registration_returns_none_for_unknown(self):
        """get_connector_registration returns None for unregistered types."""
        assert get_connector_registration("nonexistent_xyz") is None
