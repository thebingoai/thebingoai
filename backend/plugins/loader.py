import logging
from importlib.metadata import entry_points
from typing import Optional

from fastapi import APIRouter

from backend.plugins.base import BingoPlugin

logger = logging.getLogger(__name__)

_loaded_plugins: dict[str, BingoPlugin] = {}
_connector_to_plugin: dict[str, str] = {}  # type_id -> plugin name


def _topo_sort(plugins: list[BingoPlugin]) -> list[BingoPlugin]:
    """Topological sort plugins by their declared dependencies."""
    by_name = {p.name: p for p in plugins}
    visited: set[str] = set()
    result: list[BingoPlugin] = []

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        plugin = by_name.get(name)
        if plugin is None:
            return
        for dep in plugin.dependencies:
            visit(dep)
        result.append(plugin)

    for p in plugins:
        visit(p.name)
    return result


def discover_and_load_plugins() -> None:
    """Discover plugins via entry_points(group='bingo.plugins'), topo-sort by deps, register."""
    from backend.connectors.factory import register_connector

    eps = entry_points(group="bingo.plugins")
    candidates: list[BingoPlugin] = []

    for ep in eps:
        try:
            plugin_cls = ep.load()
            plugin = plugin_cls()
            if not isinstance(plugin, BingoPlugin):
                logger.warning("Plugin '%s' does not extend BingoPlugin, skipping", ep.name)
                continue
            candidates.append(plugin)
            logger.info("Discovered plugin: %s v%s", plugin.name, plugin.version)
        except Exception:
            logger.exception("Failed to load plugin entry point '%s', skipping", ep.name)

    sorted_plugins = _topo_sort(candidates)

    for plugin in sorted_plugins:
        try:
            for reg in plugin.connectors():
                if reg.version is None:
                    reg.version = plugin.version
                register_connector(reg)
                _connector_to_plugin[reg.type_id] = plugin.name
                logger.info("Registered connector type '%s' from plugin '%s'", reg.type_id, plugin.name)

            try:
                from backend.agents.tool_registry import register_plugin_tool_builder
                for tool_name, builder in plugin.tool_builders().items():
                    register_plugin_tool_builder(tool_name, builder)
                    logger.info("Registered tool builder '%s' from plugin '%s'", tool_name, plugin.name)
            except Exception:
                logger.exception("Failed to register tool builders from plugin '%s'", plugin.name)

            plugin.on_startup()
            _loaded_plugins[plugin.name] = plugin
            logger.info("Loaded plugin: %s v%s", plugin.name, plugin.version)
        except Exception:
            logger.exception("Failed to initialize plugin '%s', skipping", plugin.name)


def import_plugin_celery_tasks() -> list[str]:
    """Import all Celery task modules declared by loaded plugins.

    Must be called after discover_and_load_plugins() so _loaded_plugins is populated.
    Returns list of successfully imported module paths.
    """
    import importlib

    imported: list[str] = []
    for plugin in _loaded_plugins.values():
        for mod_path in plugin.celery_task_modules():
            try:
                importlib.import_module(mod_path)
                imported.append(mod_path)
                logger.info("Imported Celery task module '%s' from plugin '%s'", mod_path, plugin.name)
            except Exception:
                logger.exception("Failed to import task module '%s' from plugin '%s'", mod_path, plugin.name)
    return imported


def get_plugin_routers() -> list[tuple[APIRouter, str]]:
    """Return all API routers from loaded plugins for mounting."""
    routers: list[tuple[APIRouter, str]] = []
    for plugin in _loaded_plugins.values():
        try:
            routers.extend(plugin.api_routers())
        except Exception:
            logger.exception("Failed to get routers from plugin '%s'", plugin.name)
    return routers


def get_loaded_plugins() -> dict[str, BingoPlugin]:
    """Return dict of loaded plugins by name."""
    return dict(_loaded_plugins)


def get_plugin_for_connector(type_id: str) -> Optional[BingoPlugin]:
    """Find the plugin that registered a given connector type_id."""
    plugin_name = _connector_to_plugin.get(type_id)
    if plugin_name:
        return _loaded_plugins.get(plugin_name)
    return None


async def fire_chat_response_hooks(
    *, user_id: str, thread_id: str, user_message: str, assistant_message: str,
) -> None:
    """Fire on_chat_response on all loaded plugins. Errors are logged, not raised."""
    for plugin in _loaded_plugins.values():
        try:
            await plugin.on_chat_response(
                user_id=user_id,
                thread_id=thread_id,
                user_message=user_message,
                assistant_message=assistant_message,
            )
        except Exception as exc:
            logger.warning("Plugin %s on_chat_response error: %s", plugin.name, exc)


def shutdown_plugins() -> None:
    """Call on_shutdown for all loaded plugins."""
    for plugin in _loaded_plugins.values():
        try:
            plugin.on_shutdown()
        except Exception:
            logger.exception("Error shutting down plugin '%s'", plugin.name)
