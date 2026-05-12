"""Tests for the DISABLE_LOCAL_DATA_PLANE lockdown path in data_plane_service."""
import json
import logging
import uuid

import pytest

from backend.data_plane.bigquery_gcs import BigQueryGCSPlane
from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.models.data_plane import DataPlaneModel
from backend.models.organization import Organization
from backend.models.user import User
from backend.services import data_plane_service
from backend.services.data_plane_service import (
    _internal_gcp_plane,
    _read_internal_sa,
    get_default_plane,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def org(db_session):
    o = Organization(id=str(uuid.uuid4()), name=f"org-{uuid.uuid4()}")
    db_session.add(o)
    db_session.commit()
    return o


@pytest.fixture
def org_user(db_session, org):
    u = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4()}@example.com",
        auth_provider="sso",
        org_id=org.id,
    )
    db_session.add(u)
    db_session.commit()
    return u


@pytest.fixture
def sa_json_file(tmp_path):
    """Write a minimal SA JSON to disk and return its path."""
    p = tmp_path / "internal-sa.json"
    p.write_text(json.dumps({
        "type": "service_account",
        "project_id": "bingo-internal-test",
        "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
        "client_email": "internal@bingo-internal-test.iam.gserviceaccount.com",
    }))
    return p


@pytest.fixture
def lockdown_settings(monkeypatch, sa_json_file):
    """Apply settings as if DISABLE_LOCAL_DATA_PLANE=true is configured correctly."""
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", "bingo-internal-test")
    monkeypatch.setattr(settings, "internal_gcs_bucket", "bingo-internal-test-bucket")
    monkeypatch.setattr(settings, "internal_bq_dataset", "bingo_internal_test")
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(sa_json_file))
    return settings


# ── _read_internal_sa ─────────────────────────────────────────────────────


def test_read_internal_sa_returns_file_contents(sa_json_file):
    contents = _read_internal_sa(str(sa_json_file))
    assert "bingo-internal-test" in contents
    assert json.loads(contents)["type"] == "service_account"


def test_read_internal_sa_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _read_internal_sa(str(tmp_path / "nope.json"))


# ── _internal_gcp_plane ────────────────────────────────────────────────────


def test_internal_gcp_plane_built_from_settings(lockdown_settings):
    plane = _internal_gcp_plane()

    assert isinstance(plane, BigQueryGCSPlane)
    assert plane._project == "bingo-internal-test"
    assert plane._bucket_name == "bingo-internal-test-bucket"
    assert plane._dataset == "bingo_internal_test"
    assert json.loads(plane._sa_json)["client_email"].endswith(
        "iam.gserviceaccount.com"
    )


# ── _default_fallback via get_default_plane ───────────────────────────────


def test_no_rows_with_lockdown_returns_internal_plane(db_session, org_user, lockdown_settings):
    """When DISABLE_LOCAL_DATA_PLANE=true and no rows exist, fall back to internal GCP."""
    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)

    assert isinstance(plane, BigQueryGCSPlane)
    assert plane._project == "bingo-internal-test"


def test_no_rows_without_lockdown_returns_local_plane(db_session, org_user, monkeypatch):
    """Dev default: no rows + lockdown=false → LocalFilesystemDataPlane (regression guard)."""
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False)

    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)

    assert isinstance(plane, LocalFilesystemDataPlane)
