from unittest.mock import patch


def test_post_brief_returns_202_with_briefing_id(authenticated_client, db_session, sample_dashboard):
    with patch("backend.api.briefings.generate_briefing") as task_mock:
        resp = authenticated_client.post(f"/api/dashboards/{sample_dashboard.id}/brief")
    assert resp.status_code == 202
    body = resp.json()
    assert "briefing_id" in body
    assert body["status"] == "generating"
    task_mock.delay.assert_called_once_with(body["briefing_id"])


def test_post_brief_returns_existing_inflight(authenticated_client, db_session, sample_dashboard):
    with patch("backend.api.briefings.generate_briefing"):
        first = authenticated_client.post(f"/api/dashboards/{sample_dashboard.id}/brief").json()

    with patch("backend.api.briefings.generate_briefing") as task_mock:
        second = authenticated_client.post(f"/api/dashboards/{sample_dashboard.id}/brief").json()
    assert second["briefing_id"] == first["briefing_id"]
    task_mock.delay.assert_not_called()


def test_post_brief_404_when_dashboard_missing(authenticated_client):
    resp = authenticated_client.post("/api/dashboards/999999/brief")
    assert resp.status_code == 404


def test_get_briefing_returns_payload_when_ready(authenticated_client, db_session, sample_dashboard, sample_user):
    from backend.models.briefing import Briefing
    b = Briefing(
        user_id=sample_user.id,
        dashboard_id=sample_dashboard.id,
        source="manual",
        status="ready",
        payload={
            "headline": "x", "deck": "y",
            "kpis": [], "sections": [{"heading": "1", "prose": "p"}],
            "key_takeaways": ["a", "b", "c"],
        },
    )
    db_session.add(b); db_session.commit()

    resp = authenticated_client.get(f"/api/briefings/{b.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["payload"]["headline"] == "x"


def test_get_briefing_404_when_owned_by_another_user(authenticated_client, db_session, sample_dashboard, other_user):
    from backend.models.briefing import Briefing
    b = Briefing(
        user_id=other_user.id,
        dashboard_id=sample_dashboard.id,
        source="manual",
        status="ready",
    )
    db_session.add(b); db_session.commit()
    resp = authenticated_client.get(f"/api/briefings/{b.id}")
    assert resp.status_code == 404
