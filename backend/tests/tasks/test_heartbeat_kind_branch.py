from unittest.mock import patch, MagicMock
from datetime import datetime
from backend.tasks.heartbeat_tasks import dispatch_heartbeat_jobs


def test_briefing_kind_dispatches_briefing_task():
    job = MagicMock(
        id="job-1", user_id="u1", agent_type=None, kind="briefing",
        cron_expression="0 9 * * MON", is_active=True, next_run_at=datetime(2026, 5, 5),
        prompt="analyze dashboard 42 ...",
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [job]

    with patch("backend.tasks.heartbeat_tasks.SessionLocal", return_value=db), \
         patch("backend.tasks.heartbeat_tasks.execute_heartbeat_briefing.delay") as brief_delay, \
         patch("backend.tasks.heartbeat_tasks.execute_heartbeat_job.delay") as orch_delay:
        dispatch_heartbeat_jobs()

    brief_delay.assert_called_once_with("job-1")
    orch_delay.assert_not_called()
