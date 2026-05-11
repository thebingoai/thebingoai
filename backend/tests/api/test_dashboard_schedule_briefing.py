def test_analysis_schedule_creates_briefing_kind_job(authenticated_client, db_session, sample_dashboard):
    from backend.models.heartbeat_job import HeartbeatJob

    resp = authenticated_client.post(
        f"/api/dashboards/{sample_dashboard.id}/analysis-schedule",
        json={"schedule_type": "preset", "schedule_value": "daily"},
    )
    assert resp.status_code == 201

    job = db_session.query(HeartbeatJob).filter(HeartbeatJob.id == resp.json()["job_id"]).first()
    assert job.kind == "briefing"
