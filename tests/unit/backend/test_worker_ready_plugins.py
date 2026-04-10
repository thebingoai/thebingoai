"""Test that the Celery worker_process_init signal loads plugins and imports task modules."""

from unittest.mock import patch, MagicMock


def test_worker_process_init_loads_plugins():
    """Verify on_worker_process_init calls discover_and_load_plugins."""
    with patch("backend.plugins.loader.discover_and_load_plugins") as mock_load, \
         patch("backend.plugins.loader.import_plugin_celery_tasks", return_value=[]):
        from backend.tasks.upload_tasks import on_worker_process_init
        on_worker_process_init(sender=None)
        mock_load.assert_called_once()


def test_worker_process_init_imports_plugin_tasks():
    """Verify on_worker_process_init calls import_plugin_celery_tasks after loading plugins."""
    with patch("backend.plugins.loader.discover_and_load_plugins"), \
         patch("backend.plugins.loader.import_plugin_celery_tasks", return_value=["some.tasks"]) as mock_import:
        from backend.tasks.upload_tasks import on_worker_process_init
        on_worker_process_init(sender=None)
        mock_import.assert_called_once()


def test_import_plugin_celery_tasks_imports_declared_modules():
    """Verify import_plugin_celery_tasks imports modules declared by loaded plugins."""
    from backend.plugins.loader import _loaded_plugins, import_plugin_celery_tasks

    mock_plugin = MagicMock()
    mock_plugin.name = "test-plugin"
    mock_plugin.celery_task_modules.return_value = ["test_plugin.tasks"]

    original = dict(_loaded_plugins)
    _loaded_plugins["test-plugin"] = mock_plugin
    try:
        with patch("importlib.import_module") as mock_import:
            result = import_plugin_celery_tasks()
            mock_import.assert_called_once_with("test_plugin.tasks")
            assert result == ["test_plugin.tasks"]
    finally:
        _loaded_plugins.clear()
        _loaded_plugins.update(original)


def test_import_plugin_celery_tasks_handles_import_error():
    """Verify import_plugin_celery_tasks continues on import failure."""
    from backend.plugins.loader import _loaded_plugins, import_plugin_celery_tasks

    mock_plugin = MagicMock()
    mock_plugin.name = "bad-plugin"
    mock_plugin.celery_task_modules.return_value = ["nonexistent.module"]

    original = dict(_loaded_plugins)
    _loaded_plugins["bad-plugin"] = mock_plugin
    try:
        with patch("importlib.import_module", side_effect=ImportError("no such module")):
            result = import_plugin_celery_tasks()
            assert result == []
    finally:
        _loaded_plugins.clear()
        _loaded_plugins.update(original)
