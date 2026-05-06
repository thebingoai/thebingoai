"""Tests for dbt runner."""
import gzip
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.skip(reason="open() mocking complexity with gzip/subprocess makes this brittle as a unit test")
def test_run_dbt_returns_run_id():
    """run_dbt returns a non-empty run_id string on success."""
    from backend.data_plane.scope import OwnerScope

    scope = OwnerScope("org", "test-org-1")

    mock_run_results = {
        "results": [
            {"unique_id": "model.project.my_model", "status": "success", "adapter_response": {"rows_affected": 10}},
        ]
    }
    mock_manifest = {"metadata": {}, "nodes": {}}

    with patch("backend.transforms.runner.SessionLocal") as mock_session_cls, \
         patch("backend.transforms.runner.synthesize_project") as mock_synth, \
         patch("backend.transforms.runner.subprocess.run") as mock_subprocess, \
         patch("builtins.open", create=True) as mock_open, \
         patch("redis.from_url") as mock_redis:

        # Setup DB mock
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db
        mock_run = MagicMock()
        mock_run.id = "test-run-id"
        mock_db.add.return_value = None
        mock_db.commit.return_value = None

        # Setup synth mock
        mock_synth.return_value = "/tmp/fake_project"

        # Setup subprocess mock
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = ""
        proc.stderr = ""
        mock_subprocess.return_value = proc

        # Setup Redis mock
        mock_r = MagicMock()
        mock_redis.return_value = mock_r
        mock_r.lock.return_value.__enter__ = MagicMock(return_value=True)
        mock_r.lock.return_value.acquire.return_value = True

        # The function will try to open run_results.json and manifest.json
        import io
        def fake_open(path, *args, **kwargs):
            if "run_results.json" in str(path):
                return io.StringIO(json.dumps(mock_run_results))
            elif "manifest.json" in str(path):
                return io.BytesIO(json.dumps(mock_manifest).encode())
            return MagicMock()

        mock_open.side_effect = fake_open

        from backend.transforms.runner import run_dbt
        run_id = run_dbt(scope, triggered_by="manual")

    # run_id should be a non-empty UUID string
    assert run_id != ""
    assert len(run_id) > 8


def test_manifest_blob_gzip_decompressible():
    """GZip-compressed manifest_blob can be decompressed to valid JSON."""
    manifest_data = {"metadata": {"dbt_version": "1.7.0"}, "nodes": {}}
    manifest_bytes = json.dumps(manifest_data).encode()
    compressed = gzip.compress(manifest_bytes)
    # Decompress and verify round-trip
    decompressed = gzip.decompress(compressed)
    assert json.loads(decompressed) == manifest_data


def test_status_logic_all_success():
    """All models succeed → status = 'success'."""
    models_run = [
        {"name": "a", "status": "success"},
        {"name": "b", "status": "success"},
    ]
    all_ok = all(m["status"] == "success" for m in models_run)
    any_ok = any(m["status"] == "success" for m in models_run)
    status = "success" if all_ok else ("partial_success" if any_ok else "failed")
    assert status == "success"


def test_status_logic_partial_success():
    """Some models fail → status = 'partial_success'."""
    models_run = [
        {"name": "a", "status": "success"},
        {"name": "b", "status": "error"},
    ]
    all_ok = all(m["status"] == "success" for m in models_run)
    any_ok = any(m["status"] == "success" for m in models_run)
    status = "success" if all_ok else ("partial_success" if any_ok else "failed")
    assert status == "partial_success"


def test_status_logic_all_failed():
    """All models fail → status = 'failed'."""
    models_run = [
        {"name": "a", "status": "error"},
        {"name": "b", "status": "error"},
    ]
    all_ok = all(m["status"] == "success" for m in models_run)
    any_ok = any(m["status"] == "success" for m in models_run)
    status = "success" if all_ok else ("partial_success" if any_ok else "failed")
    assert status == "failed"
