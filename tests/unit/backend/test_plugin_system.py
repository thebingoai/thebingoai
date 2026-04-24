"""Unit tests for the plugin architecture: DatabaseType registry, connector factory,
plugin loader, graceful degradation, and schema validation."""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import APIRouter
from pydantic import ValidationError

from backend.models.database_connection import DatabaseType
from backend.plugins.base import BingoPlugin, ConnectorRegistration
from backend.plugins import loader
from backend.connectors import factory
from backend.agents import tool_registry


# ---------------------------------------------------------------------------
# Helpers & stubs
# ---------------------------------------------------------------------------

class DummyConnector:
    """Minimal connector stub for testing registration."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


class DummyConnectorWithFromConnection:
    """Connector that implements from_connection classmethod."""
    def __init__(self, connection):
        self.connection = connection

    @classmethod
    def from_connection(cls, connection):
        return cls(connection)

    def close(self):
        pass


class DummyPlugin(BingoPlugin):
    """Concrete plugin for testing."""
    @property
    def name(self):
        return "test-plugin"

    @property
    def version(self):
        return "0.1.0"

    def connectors(self):
        return [ConnectorRegistration(
            type_id="testdb",
            display_name="TestDB",
            description="A test connector",
            default_port=9999,
            badge_variant="info",
            connector_class=DummyConnector,
        )]


class PluginA(BingoPlugin):
    @property
    def name(self):
        return "plugin-a"

    @property
    def version(self):
        return "1.0"


class PluginB(BingoPlugin):
    @property
    def name(self):
        return "plugin-b"

    @property
    def version(self):
        return "1.0"

    @property
    def dependencies(self):
        return ["plugin-a"]


def _make_entry_point(plugin_cls):
    """Create a mock entry point that loads a plugin class."""
    ep = MagicMock()
    ep.name = plugin_cls.__name__
    ep.load.return_value = plugin_cls
    return ep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_plugin_state():
    """Reset module-level plugin and connector registries between tests."""
    original_plugins = loader._loaded_plugins.copy()
    original_connectors = factory._CONNECTORS.copy()
    original_all = DatabaseType._all.copy()
    original_tool_builders = tool_registry._PLUGIN_TOOL_BUILDERS.copy()
    # Snapshot dynamic attrs on DatabaseType
    original_attrs = {
        k: v for k, v in vars(DatabaseType).items()
        if not k.startswith("_") and isinstance(v, str)
    }

    yield

    loader._loaded_plugins.clear()
    loader._loaded_plugins.update(original_plugins)
    factory._CONNECTORS.clear()
    factory._CONNECTORS.update(original_connectors)
    DatabaseType._all.clear()
    DatabaseType._all.update(original_all)
    tool_registry._PLUGIN_TOOL_BUILDERS.clear()
    tool_registry._PLUGIN_TOOL_BUILDERS.update(original_tool_builders)
    # Remove any dynamic attrs added during the test
    current_attrs = {
        k for k, v in vars(DatabaseType).items()
        if not k.startswith("_") and isinstance(v, str)
    }
    for attr in current_attrs - set(original_attrs):
        delattr(DatabaseType, attr)


# ===========================================================================
# Section 1: DatabaseType Registry
# ===========================================================================

class TestDatabaseTypeRegistry:
    def test_builtin_types_registered(self):
        assert DatabaseType.POSTGRES == "postgres"
        assert DatabaseType.MYSQL == "mysql"
        assert DatabaseType.is_valid("postgres")
        assert DatabaseType.is_valid("mysql")

    def test_register_custom_type(self):
        DatabaseType.register("mongodb", "MongoDB")
        assert DatabaseType.MONGODB == "mongodb"
        assert DatabaseType.is_valid("mongodb")
        assert DatabaseType._all["mongodb"] == "MongoDB"

    def test_is_valid_rejects_unknown(self):
        assert not DatabaseType.is_valid("snowflake")

    def test_register_idempotent(self):
        DatabaseType.register("redis", "Redis")
        DatabaseType.register("redis", "Redis")
        assert DatabaseType._all["redis"] == "Redis"
        # Only one entry
        assert list(DatabaseType._all.values()).count("Redis") == 1


# ===========================================================================
# Section 2: Connector Factory
# ===========================================================================

class TestConnectorFactory:
    def test_core_types_registered_on_import(self):
        types = factory.get_available_types()
        ids = [t["id"] for t in types]
        assert "postgres" in ids
        assert "mysql" in ids
        pg = next(t for t in types if t["id"] == "postgres")
        assert pg["display_name"] == "PostgreSQL"
        assert pg["default_port"] == 5432

    def test_register_connector_adds_type(self):
        reg = ConnectorRegistration(
            type_id="testdb",
            display_name="TestDB",
            description="Test",
            default_port=9999,
            badge_variant="info",
            connector_class=DummyConnector,
        )
        factory.register_connector(reg)
        ids = [t["id"] for t in factory.get_available_types()]
        assert "testdb" in ids
        assert DatabaseType.is_valid("testdb")

    def test_get_connector_registration_found(self):
        reg = factory.get_connector_registration("postgres")
        assert reg is not None
        assert reg.type_id == "postgres"

    def test_get_connector_registration_missing(self):
        assert factory.get_connector_registration("nosuchdb") is None

    def test_get_connector_for_connection_standard(self):
        """Standard connector created via host/port/database kwargs."""
        reg = ConnectorRegistration(
            type_id="testdb",
            display_name="TestDB",
            description="Test",
            default_port=9999,
            badge_variant="info",
            connector_class=DummyConnector,
        )
        factory.register_connector(reg)

        mock_conn = MagicMock()
        mock_conn.db_type = "testdb"
        mock_conn.host = "localhost"
        mock_conn.port = 9999
        mock_conn.database = "mydb"
        mock_conn.username = "user"
        mock_conn.password = "pass"
        mock_conn.ssl_enabled = False
        mock_conn.ssl_ca_cert = None

        connector = factory.get_connector_for_connection(mock_conn)
        assert isinstance(connector, DummyConnector)
        assert connector.kwargs["host"] == "localhost"
        assert connector.kwargs["port"] == 9999

    def test_get_connector_for_connection_from_connection(self):
        """Connector with from_connection() classmethod uses it instead of standard init."""
        reg = ConnectorRegistration(
            type_id="customdb",
            display_name="CustomDB",
            description="Custom",
            default_port=1234,
            badge_variant="success",
            connector_class=DummyConnectorWithFromConnection,
        )
        factory.register_connector(reg)

        mock_conn = MagicMock()
        mock_conn.db_type = "customdb"

        connector = factory.get_connector_for_connection(mock_conn)
        assert isinstance(connector, DummyConnectorWithFromConnection)
        assert connector.connection is mock_conn


# ===========================================================================
# Section 3: Plugin Loader
# ===========================================================================

class TestPluginLoader:
    def test_topo_sort_no_deps(self):
        a, b = PluginA(), PluginB.__bases__[0]  # Avoid using B (has dep)
        a_inst = PluginA()
        # Create another plugin with no deps
        class PluginC(BingoPlugin):
            @property
            def name(self):
                return "plugin-c"
            @property
            def version(self):
                return "1.0"

        c_inst = PluginC()
        result = loader._topo_sort([a_inst, c_inst])
        names = [p.name for p in result]
        assert "plugin-a" in names
        assert "plugin-c" in names
        assert len(result) == 2

    def test_topo_sort_with_deps(self):
        a, b = PluginA(), PluginB()
        result = loader._topo_sort([b, a])
        names = [p.name for p in result]
        assert names.index("plugin-a") < names.index("plugin-b")

    def test_discover_and_load_registers_connectors(self):
        with patch.object(loader, "entry_points", return_value=[_make_entry_point(DummyPlugin)]):
            loader.discover_and_load_plugins()

        assert DatabaseType.is_valid("testdb")
        ids = [t["id"] for t in factory.get_available_types()]
        assert "testdb" in ids
        assert "test-plugin" in loader._loaded_plugins

    def test_discover_skips_non_bingo_plugin(self):
        class NotAPlugin:
            pass

        ep = MagicMock()
        ep.name = "bad-plugin"
        ep.load.return_value = NotAPlugin

        with patch.object(loader, "entry_points", return_value=[ep]):
            loader.discover_and_load_plugins()

        assert "bad-plugin" not in loader._loaded_plugins

    def test_discover_skips_failing_plugin(self):
        ep_bad = MagicMock()
        ep_bad.name = "broken"
        ep_bad.load.side_effect = ImportError("missing module")

        ep_good = _make_entry_point(DummyPlugin)

        with patch.object(loader, "entry_points", return_value=[ep_bad, ep_good]):
            loader.discover_and_load_plugins()

        # Good plugin loaded, bad one skipped
        assert "test-plugin" in loader._loaded_plugins
        assert "broken" not in loader._loaded_plugins

    def test_get_plugin_routers(self):
        router = APIRouter()

        class RouterPlugin(BingoPlugin):
            @property
            def name(self):
                return "router-plugin"

            @property
            def version(self):
                return "0.1.0"

            def api_routers(self):
                return [(router, "/api/test")]

        # Isolate from plugins loaded by prior tests / real entry points
        original = dict(loader._loaded_plugins)
        loader._loaded_plugins.clear()
        try:
            with patch.object(loader, "entry_points", return_value=[_make_entry_point(RouterPlugin)]):
                loader.discover_and_load_plugins()

            routers = loader.get_plugin_routers()
            assert len(routers) == 1
            assert routers[0][0] is router
            assert routers[0][1] == "/api/test"
        finally:
            loader._loaded_plugins.clear()
            loader._loaded_plugins.update(original)

    def test_tool_builders_default_empty(self):
        """BingoPlugin.tool_builders() returns empty dict by default."""
        plugin = PluginA()
        assert plugin.tool_builders() == {}

    def test_tool_builders_registered_by_loader(self):
        """Plugin tool builders are registered during discover_and_load_plugins."""
        def my_builder(ctx):
            return []

        class ToolPlugin(BingoPlugin):
            @property
            def name(self):
                return "tool-plugin"

            @property
            def version(self):
                return "0.1.0"

            def tool_builders(self):
                return {"my_tool": my_builder}

        with patch.object(loader, "entry_points", return_value=[_make_entry_point(ToolPlugin)]):
            loader.discover_and_load_plugins()

        builders = tool_registry.get_plugin_tool_builders()
        assert "my_tool" in builders
        assert builders["my_tool"] is my_builder

    def test_failing_tool_builder_registration_skipped(self):
        """Plugin whose tool_builders() raises doesn't prevent other plugins from loading."""
        class FailToolPlugin(BingoPlugin):
            @property
            def name(self):
                return "fail-tool"

            @property
            def version(self):
                return "0.1.0"

            def tool_builders(self):
                raise RuntimeError("tool builder boom")

        with patch.object(
            loader,
            "entry_points",
            return_value=[_make_entry_point(FailToolPlugin), _make_entry_point(DummyPlugin)],
        ):
            loader.discover_and_load_plugins()

        assert "test-plugin" in loader._loaded_plugins

    def test_get_plugin_tool_builders_returns_copy(self):
        """Mutating returned dict doesn't affect internal state."""
        def builder_fn(ctx):
            return []

        tool_registry.register_plugin_tool_builder("test_tool", builder_fn)
        result = tool_registry.get_plugin_tool_builders()
        result["injected"] = lambda ctx: []

        fresh = tool_registry.get_plugin_tool_builders()
        assert "injected" not in fresh
        assert "test_tool" in fresh


# ===========================================================================
# Section 4: Graceful Degradation
# ===========================================================================

class TestGracefulDegradation:
    def test_core_works_without_plugins(self):
        # Isolate from plugins loaded by prior tests / real entry points
        original = dict(loader._loaded_plugins)
        loader._loaded_plugins.clear()
        try:
            with patch.object(loader, "entry_points", return_value=[]):
                loader.discover_and_load_plugins()

            ids = [t["id"] for t in factory.get_available_types()]
            assert "postgres" in ids
            assert "mysql" in ids
            assert len(loader._loaded_plugins) == 0
        finally:
            loader._loaded_plugins.clear()
            loader._loaded_plugins.update(original)

    def test_failing_plugin_doesnt_crash_core(self):
        class FailStartupPlugin(BingoPlugin):
            @property
            def name(self):
                return "fail-startup"

            @property
            def version(self):
                return "0.1.0"

            def on_startup(self):
                raise RuntimeError("startup boom")

        with patch.object(
            loader,
            "entry_points",
            return_value=[_make_entry_point(FailStartupPlugin), _make_entry_point(DummyPlugin)],
        ):
            loader.discover_and_load_plugins()

        # Failing plugin not loaded, good one is
        assert "fail-startup" not in loader._loaded_plugins
        assert "test-plugin" in loader._loaded_plugins

    def test_shutdown_handles_plugin_errors(self):
        class FailShutdownPlugin(BingoPlugin):
            @property
            def name(self):
                return "fail-shutdown"

            @property
            def version(self):
                return "0.1.0"

            def on_shutdown(self):
                raise RuntimeError("shutdown boom")

        # Manually add to loaded plugins
        loader._loaded_plugins["fail-shutdown"] = FailShutdownPlugin()

        # Should not raise
        loader.shutdown_plugins()


# ===========================================================================
# Section 5: Schema Validation
# ===========================================================================

class TestSchemaValidation:
    def test_connection_create_valid_type(self):
        from backend.schemas.connection import ConnectionCreate

        conn = ConnectionCreate(
            name="My PG",
            db_type="postgres",
            host="localhost",
            port=5432,
            database="mydb",
            username="user",
            password="pass",
        )
        assert conn.db_type == "postgres"

    def test_connection_create_invalid_type(self):
        from backend.schemas.connection import ConnectionCreate

        with pytest.raises(ValidationError) as exc_info:
            ConnectionCreate(
                name="Bad",
                db_type="nosuchdb",
                host="localhost",
                port=5432,
                database="mydb",
                username="user",
                password="pass",
            )
        assert "Unsupported database type" in str(exc_info.value)
