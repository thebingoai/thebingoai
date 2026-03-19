import logging
from importlib.metadata import entry_points
from typing import Optional

from fastapi import APIRouter

from backend.plugins.base import BingoPlugin

logger = logging.getLogger(__name__)

_loaded_plugins: dict[str, BingoPlugin] = {}


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
                register_connector(reg)
                logger.info("Registered connector type '%s' from plugin '%s'", reg.type_id, plugin.name)

            plugin.on_startup()
            _loaded_plugins[plugin.name] = plugin
            logger.info("Loaded plugin: %s v%s", plugin.name, plugin.version)
        except Exception:
            logger.exception("Failed to initialize plugin '%s', skipping", plugin.name)


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


def shutdown_plugins() -> None:
    """Call on_shutdown for all loaded plugins."""
    for plugin in _loaded_plugins.values():
        try:
            plugin.on_shutdown()
        except Exception:
            logger.exception("Error shutting down plugin '%s'", plugin.name)
