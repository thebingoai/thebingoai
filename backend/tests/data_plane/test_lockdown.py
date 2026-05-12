"""Tests for the DISABLE_LOCAL_DATA_PLANE lockdown path in data_plane_service.

Shape A: there is no env-driven singleton fallback. When the resolver finds
no row and lockdown is on, it raises ``NoPlaneProvisionedError``. When
lockdown is off, the historical dev-convenience ``LocalFilesystemDataPlane``
is returned. A ``local_filesystem`` row under lockdown raises
``LocalPlaneUnderLockdownError`` instead of being silently rerouted.
"""
import json
import uuid

import pytest

from backend.data_plane.errors import (
    LocalPlaneUnderLockdownError,
    NoPlaneProvisionedError,
)
from backend.data_plane.local_filesystem import LocalFilesystemDataPlane
from backend.data_plane.scope import OwnerScope
from backend.models.data_plane import DataPlaneModel
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.data_plane_service import (
    check_internal_gcp_config,
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
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(sa_json_file))
    return settings


# ── No-row behaviour ──────────────────────────────────────────────────────


def test_no_rows_under_lockdown_raises(db_session, org_user, lockdown_settings):
    """Lockdown on + no rows → NoPlaneProvisionedError with the requested scope."""
    with pytest.raises(NoPlaneProvisionedError) as exc:
        get_default_plane(OwnerScope("user", org_user.id), db_session)
    assert exc.value.scope.kind == "user"
    assert exc.value.scope.id == org_user.id


def test_no_rows_without_lockdown_returns_local_plane(db_session, org_user, monkeypatch):
    """Dev default: no rows + lockdown=false → LocalFilesystemDataPlane (regression guard)."""
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False)

    plane = get_default_plane(OwnerScope("user", org_user.id), db_session)
    assert isinstance(plane, LocalFilesystemDataPlane)


# ── _instantiate strictness ───────────────────────────────────────────────


def test_local_filesystem_row_refused_under_lockdown(db_session, org, lockdown_settings):
    """An is_default local_filesystem row at org scope raises under lockdown."""
    row = DataPlaneModel(
        id=str(uuid.uuid4()),
        owner_scope_kind="org",
        owner_scope_id=org.id,
        type="local_filesystem",
        config={"root_path": "/tmp/should-not-be-used"},
        is_default=True,
    )
    db_session.add(row)
    db_session.commit()

    with pytest.raises(LocalPlaneUnderLockdownError) as exc:
        get_default_plane(OwnerScope("org", org.id), db_session)
    assert exc.value.row_id == row.id


# ── check_internal_gcp_config ─────────────────────────────────────────────


def test_check_internal_gcp_config_noop_when_lockdown_off(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False)
    check_internal_gcp_config()  # no raise


def test_check_internal_gcp_config_raises_when_project_missing(monkeypatch, sa_json_file):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", None)
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(sa_json_file))
    with pytest.raises(RuntimeError, match="INTERNAL_GCP_PROJECT"):
        check_internal_gcp_config()


def test_check_internal_gcp_config_raises_when_sa_path_missing(monkeypatch, tmp_path):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", "x")
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(tmp_path / "nope.json"))
    with pytest.raises(RuntimeError, match="INTERNAL_GCP_SA_JSON_PATH"):
        check_internal_gcp_config()


def test_check_internal_gcp_config_drops_bucket_dataset_preconditions(monkeypatch, sa_json_file):
    """Shape A: bucket/dataset live on data_planes rows, not env. Config check must not require them."""
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", "x")
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(sa_json_file))
    monkeypatch.setattr(settings, "internal_gcs_bucket", None)
    monkeypatch.setattr(settings, "internal_bq_dataset", None)
    check_internal_gcp_config()  # no raise
