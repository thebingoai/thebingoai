from backend.models.briefing import Briefing


def test_briefing_has_required_columns():
    cols = {c.name for c in Briefing.__table__.columns}
    assert {"id", "user_id", "dashboard_id", "source", "heartbeat_job_id",
            "date_range_from", "date_range_to", "payload", "status",
            "error", "created_at"}.issubset(cols)
