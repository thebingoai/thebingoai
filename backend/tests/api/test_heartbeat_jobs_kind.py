"""Verify HeartbeatJobResponse exposes the `kind` discriminator
(needed by the Settings → Jobs UI to badge briefing-kind jobs)."""

from backend.models.heartbeat_job import HeartbeatJob


def _create_job(db_session, user_id, *, kind: str, name: str) -> HeartbeatJob:
    job = HeartbeatJob(
        user_id=user_id,
        name=name,
        prompt="do something",
        schedule_type="preset",
        schedule_value="daily",
        cron_expression="0 9 * * *",
        kind=kind,
        is_active=True,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_list_heartbeat_jobs_returns_kind_chat_and_briefing(authenticated_client, db_session, sample_user):
    _create_job(db_session, sample_user.id, kind="chat", name="standup")
    _create_job(db_session, sample_user.id, kind="briefing", name="Dashboard Analysis: X")

    resp = authenticated_client.get("/api/heartbeat-jobs")
    assert resp.status_code == 200
    rows = resp.json()
    by_name = {r["name"]: r for r in rows}
    assert by_name["standup"]["kind"] == "chat"
    assert by_name["Dashboard Analysis: X"]["kind"] == "briefing"


def test_get_single_job_returns_kind(authenticated_client, db_session, sample_user):
    job = _create_job(db_session, sample_user.id, kind="briefing", name="brief")
    resp = authenticated_client.get(f"/api/heartbeat-jobs/{job.id}")
    assert resp.status_code == 200
    assert resp.json()["kind"] == "briefing"


def test_create_job_defaults_kind_to_chat(authenticated_client):
    resp = authenticated_client.post(
        "/api/heartbeat-jobs",
        json={
            "name": "smoke",
            "prompt": "ping",
            "schedule_type": "preset",
            "schedule_value": "daily",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["kind"] == "chat"
