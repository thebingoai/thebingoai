"""Test that the Celery worker_process_init signal loads plugins."""

from unittest.mock import patch


def test_worker_process_init_loads_plugins():
    """Verify on_worker_process_init calls discover_and_load_plugins."""
    with patch("backend.plugins.loader.discover_and_load_plugins") as mock_load:
        from backend.tasks.upload_tasks import on_worker_process_init
        on_worker_process_init(sender=None)
        mock_load.assert_called_once()
