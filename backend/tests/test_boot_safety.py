"""Boot-safety preconditions for DISABLE_LOCAL_DATA_PLANE."""
import json

import pytest

from backend.services.data_plane_service import check_internal_gcp_config


@pytest.fixture
def sa_json_file(tmp_path):
    p = tmp_path / "internal-sa.json"
    p.write_text(json.dumps({"type": "service_account", "project_id": "test"}))
    return p


def test_lockdown_off_is_a_noop(monkeypatch):
    """When DISABLE_LOCAL_DATA_PLANE=false, the check returns without raising
    regardless of internal-GCP env state (dev path)."""
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", False)
    monkeypatch.setattr(settings, "internal_gcp_project", None)
    monkeypatch.setattr(settings, "internal_gcs_bucket", None)
    monkeypatch.setattr(settings, "internal_bq_dataset", None)
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", None)

    check_internal_gcp_config()  # must not raise


@pytest.mark.parametrize(
    "missing_field, env_name",
    [
        ("internal_gcp_project", "INTERNAL_GCP_PROJECT"),
        ("internal_gcs_bucket", "INTERNAL_GCS_BUCKET"),
        ("internal_bq_dataset", "INTERNAL_BQ_DATASET"),
    ],
)
def test_missing_internal_env_raises(monkeypatch, sa_json_file, missing_field, env_name):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", "bingo-test")
    monkeypatch.setattr(settings, "internal_gcs_bucket", "bingo-test-bucket")
    monkeypatch.setattr(settings, "internal_bq_dataset", "bingo_test")
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(sa_json_file))
    monkeypatch.setattr(settings, missing_field, None)

    with pytest.raises(RuntimeError, match=env_name):
        check_internal_gcp_config()


def test_missing_sa_file_raises(monkeypatch, tmp_path):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", "bingo-test")
    monkeypatch.setattr(settings, "internal_gcs_bucket", "bingo-test-bucket")
    monkeypatch.setattr(settings, "internal_bq_dataset", "bingo_test")
    monkeypatch.setattr(
        settings,
        "internal_gcp_sa_json_path",
        str(tmp_path / "missing.json"),
    )

    with pytest.raises(RuntimeError, match="INTERNAL_GCP_SA_JSON_PATH"):
        check_internal_gcp_config()


def test_all_set_is_a_noop(monkeypatch, sa_json_file):
    from backend.config import settings
    monkeypatch.setattr(settings, "disable_local_data_plane", True)
    monkeypatch.setattr(settings, "internal_gcp_project", "bingo-test")
    monkeypatch.setattr(settings, "internal_gcs_bucket", "bingo-test-bucket")
    monkeypatch.setattr(settings, "internal_bq_dataset", "bingo_test")
    monkeypatch.setattr(settings, "internal_gcp_sa_json_path", str(sa_json_file))

    check_internal_gcp_config()  # must not raise
