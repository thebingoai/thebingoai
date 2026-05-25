"""Integration tests for the DuckDB-cutover endpoint wiring + schema.

Covers the create-dashboard born-DuckDB hook (P3) and the residency_locked
column (P2) against the real test DB via the shared integration harness.
"""
import uuid

# Import registers the model on Base.metadata so the session-scoped test_engine
# create_all() builds the dashboard_dialect_migration table.
from backend.migration.dialect_migration import DashboardDialectMigration
from backend.models.data_plane import DataPlaneModel
from backend.models.organization import Organization


def _give_org(db_session, user):
    org = Organization(id=f"org-{uuid.uuid4()}", name=f"org-{uuid.uuid4()}")
    db_session.add(org)
    user.org_id = org.id
    db_session.commit()
    return org.id


def test_create_dashboard_marks_born_duckdb_when_flag_on(authenticated_client, db_session, sample_user, monkeypatch):
    _give_org(db_session, sample_user)
    monkeypatch.setattr(
        "backend.config.feature_flags.enabled",
        lambda org_id, flag, default=False: flag == "duckdb_widget_serving",
    )
    resp = authenticated_client.post("/api/dashboards", json={"title": "BD", "widgets": []})
    assert resp.status_code == 201
    did = resp.json()["id"]
    row = db_session.query(DashboardDialectMigration).filter_by(dashboard_id=did).first()
    assert row is not None
    assert row.status == "born_duckdb"


def test_create_dashboard_no_mark_when_flag_off(authenticated_client, db_session, sample_user, monkeypatch):
    _give_org(db_session, sample_user)
    monkeypatch.setattr("backend.config.feature_flags.enabled", lambda *a, **k: False)
    resp = authenticated_client.post("/api/dashboards", json={"title": "BD2", "widgets": []})
    assert resp.status_code == 201
    did = resp.json()["id"]
    assert db_session.query(DashboardDialectMigration).filter_by(dashboard_id=did).first() is None


def test_create_dashboard_no_mark_without_org(authenticated_client, db_session, sample_user, monkeypatch):
    # sample_user has no org_id → hook short-circuits regardless of flag.
    monkeypatch.setattr("backend.config.feature_flags.enabled", lambda *a, **k: True)
    resp = authenticated_client.post("/api/dashboards", json={"title": "BD3", "widgets": []})
    did = resp.json()["id"]
    assert db_session.query(DashboardDialectMigration).filter_by(dashboard_id=did).first() is None


def test_data_plane_residency_locked_defaults_false_and_settable(db_session):
    row = DataPlaneModel(
        owner_scope_kind="org",
        owner_scope_id=f"o-{uuid.uuid4()}",
        type="google_cloud_project",
        config={},
        is_default=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.residency_locked is False
    row.residency_locked = True
    db_session.commit()
    db_session.refresh(row)
    assert row.residency_locked is True
