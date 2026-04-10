"""Tests for connector type metadata: version, card_meta_items, changelog helpers."""

from unittest.mock import MagicMock

import pytest

from backend.api.health import APP_VERSION
from backend.connectors.factory import get_available_types
from backend.plugins.base import ConnectorRegistration, BingoPlugin
from backend.plugins.loader import get_plugin_for_connector


class TestGetAvailableTypes:

    def test_all_types_have_version(self):
        types = get_available_types()
        assert len(types) >= 3  # postgres, mysql, sqlite at minimum
        for t in types:
            assert "version" in t
            assert isinstance(t["version"], str)
            assert len(t["version"]) > 0

    def test_all_types_have_card_meta_items(self):
        types = get_available_types()
        for t in types:
            assert "card_meta_items" in t
            assert isinstance(t["card_meta_items"], list)

    def test_core_connectors_use_app_version(self):
        types = get_available_types()
        core_ids = {"postgres", "mysql", "sqlite"}
        for t in types:
            if t["id"] in core_ids:
                assert t["version"] == APP_VERSION

    def test_postgres_meta_items(self):
        types = get_available_types()
        pg = next(t for t in types if t["id"] == "postgres")
        assert pg["card_meta_items"] == ["ssl", "table_count", "schema_date"]

    def test_mysql_meta_items(self):
        types = get_available_types()
        my = next(t for t in types if t["id"] == "mysql")
        assert my["card_meta_items"] == ["ssl", "table_count", "schema_date"]

    def test_sqlite_meta_items(self):
        types = get_available_types()
        sq = next(t for t in types if t["id"] == "sqlite")
        assert sq["card_meta_items"] == ["table_count", "schema_date"]


class TestConnectorRegistrationVersion:

    def test_explicit_version_preserved(self):
        reg = ConnectorRegistration(
            type_id="test",
            display_name="Test",
            description="Test connector",
            default_port=0,
            badge_variant="info",
            connector_class=MagicMock,
            version="1.2.3",
        )
        assert reg.version == "1.2.3"

    def test_version_defaults_to_none(self):
        reg = ConnectorRegistration(
            type_id="test",
            display_name="Test",
            description="Test connector",
            default_port=0,
            badge_variant="info",
            connector_class=MagicMock,
        )
        assert reg.version is None

    def test_card_meta_items_defaults_to_none(self):
        reg = ConnectorRegistration(
            type_id="test",
            display_name="Test",
            description="Test connector",
            default_port=0,
            badge_variant="info",
            connector_class=MagicMock,
        )
        assert reg.card_meta_items is None

    def test_explicit_card_meta_items(self):
        reg = ConnectorRegistration(
            type_id="test",
            display_name="Test",
            description="Test connector",
            default_port=0,
            badge_variant="info",
            connector_class=MagicMock,
            card_meta_items=["ssl", "table_count"],
        )
        assert reg.card_meta_items == ["ssl", "table_count"]


class TestGetPluginForConnector:

    def test_returns_none_for_core_connectors(self):
        # Core connectors (postgres, mysql, sqlite) are not registered by plugins
        assert get_plugin_for_connector("postgres") is None
        assert get_plugin_for_connector("mysql") is None
        assert get_plugin_for_connector("sqlite") is None

    def test_returns_none_for_unknown_type(self):
        assert get_plugin_for_connector("nonexistent") is None
