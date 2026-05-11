"""Tests for Celery briefing tasks."""

from unittest.mock import patch, AsyncMock
from backend.tasks.briefing_tasks import generate_briefing


def test_celery_task_invokes_runner_with_briefing_id():
    with patch("backend.tasks.briefing_tasks.briefing_runner.run", new=AsyncMock()) as run_mock:
        generate_briefing.run(briefing_id=99)
    run_mock.assert_awaited_once_with(99)
