"""Tests for the Redis-backed job store service."""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from backend.models.job import JobInfo, JobStatus, JobResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job_json(
    job_id="job-1",
    status="pending",
    file_name="test.md",
    namespace="ns-1",
    progress=0,
    **overrides,
) -> str:
    """Build a JobInfo-compatible JSON string for mock Redis returns."""
    data = {
        "job_id": job_id,
        "status": status,
        "file_name": file_name,
        "namespace": namespace,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "progress": progress,
        **overrides,
    }
    return json.dumps(data)


def _make_mock_datetime():
    """Create a mock datetime that has the .UTC attribute the source expects."""
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.UTC = timezone.utc
    mock_dt.now = datetime.now
    return mock_dt


_MOCK_DATETIME = _make_mock_datetime()


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------

class TestCreateJob:
    """Tests for create_job."""

    @patch("backend.services.job_store.datetime", new=_MOCK_DATETIME)
    @patch("backend.services.job_store.redis_client")
    @patch("backend.services.job_store.settings")
    def test_creates_job_with_pending_status(self, mock_settings, mock_redis):
        """Newly created job has PENDING status."""
        mock_settings.job_ttl_seconds = 3600
        from backend.services.job_store import create_job

        job = create_job("job-1", "report.md", "user-ns")

        assert job.job_id == "job-1"
        assert job.status == JobStatus.PENDING
        assert job.file_name == "report.md"
        assert job.namespace == "user-ns"

    @patch("backend.services.job_store.datetime", new=_MOCK_DATETIME)
    @patch("backend.services.job_store.redis_client")
    @patch("backend.services.job_store.settings")
    def test_stores_in_redis_with_ttl(self, mock_settings, mock_redis):
        """create_job calls redis setex with the configured TTL."""
        mock_settings.job_ttl_seconds = 7200
        from backend.services.job_store import create_job

        create_job("job-2", "data.csv", "ns")

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "job:job-2"
        assert args[0][1] == 7200


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------

class TestGetJob:
    """Tests for get_job."""

    @patch("backend.services.job_store.redis_client")
    def test_returns_job_when_found(self, mock_redis):
        """get_job returns a JobInfo when data exists in Redis."""
        mock_redis.get.return_value = _make_job_json(job_id="job-10")
        from backend.services.job_store import get_job

        job = get_job("job-10")
        assert job is not None
        assert job.job_id == "job-10"

    @patch("backend.services.job_store.redis_client")
    def test_returns_none_when_not_found(self, mock_redis):
        """get_job returns None for a missing job ID."""
        mock_redis.get.return_value = None
        from backend.services.job_store import get_job

        assert get_job("missing") is None


# ---------------------------------------------------------------------------
# update_progress
# ---------------------------------------------------------------------------

class TestUpdateProgress:
    """Tests for update_progress."""

    @patch("backend.services.job_store.redis_client")
    @patch("backend.services.job_store.settings")
    def test_updates_progress_fields(self, mock_settings, mock_redis):
        """update_progress sets chunks_processed and progress percentage."""
        mock_settings.job_ttl_seconds = 3600
        stored = _make_job_json(job_id="job-p", status="processing")
        mock_redis.get.return_value = stored

        from backend.services.job_store import update_progress

        result = update_progress("job-p", chunks_processed=5, progress=50)
        assert result is not None
        assert result.progress == 50
        assert result.chunks_processed == 5


# ---------------------------------------------------------------------------
# complete_job
# ---------------------------------------------------------------------------

class TestCompleteJob:
    """Tests for complete_job."""

    @patch("backend.services.job_store.datetime", new=_MOCK_DATETIME)
    @patch("backend.services.job_store.redis_client")
    @patch("backend.services.job_store.settings")
    def test_sets_completed_status(self, mock_settings, mock_redis):
        """complete_job transitions status to COMPLETED with result data."""
        mock_settings.job_ttl_seconds = 3600
        stored = _make_job_json(job_id="job-c", status="processing")
        mock_redis.get.return_value = stored

        from backend.services.job_store import complete_job

        result = complete_job(
            "job-c",
            file_name="report.md",
            chunks_created=10,
            vectors_upserted=10,
            namespace="ns-1",
        )
        assert result is not None
        assert result.status == JobStatus.COMPLETED
        assert result.progress == 100
        assert result.result is not None
        assert result.result.chunks_created == 10


# ---------------------------------------------------------------------------
# fail_job
# ---------------------------------------------------------------------------

class TestFailJob:
    """Tests for fail_job."""

    @patch("backend.services.job_store.datetime", new=_MOCK_DATETIME)
    @patch("backend.services.job_store.redis_client")
    @patch("backend.services.job_store.settings")
    def test_sets_failed_status_with_error(self, mock_settings, mock_redis):
        """fail_job transitions status to FAILED and records the error message."""
        mock_settings.job_ttl_seconds = 3600
        stored = _make_job_json(job_id="job-f", status="processing")
        mock_redis.get.return_value = stored

        from backend.services.job_store import fail_job

        result = fail_job("job-f", error="Out of memory")
        assert result is not None
        assert result.status == JobStatus.FAILED
        assert result.error == "Out of memory"


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

class TestListJobs:
    """Tests for list_jobs."""

    @patch("backend.services.job_store.redis_client")
    def test_returns_jobs_for_namespace(self, mock_redis):
        """list_jobs filters by namespace when provided."""
        job_a = _make_job_json(job_id="a", namespace="ns-1")
        job_b = _make_job_json(job_id="b", namespace="ns-2")

        # Simulate scan returning two keys then finishing
        mock_redis.scan.return_value = (0, ["job:a", "job:b"])
        mock_redis.get.side_effect = [job_a, job_b]

        from backend.services.job_store import list_jobs

        jobs = list_jobs(namespace="ns-1")
        assert all(j.namespace == "ns-1" for j in jobs)

    @patch("backend.services.job_store.redis_client")
    def test_returns_empty_when_no_keys(self, mock_redis):
        """list_jobs returns an empty list when Redis has no matching keys."""
        mock_redis.scan.return_value = (0, [])

        from backend.services.job_store import list_jobs

        assert list_jobs() == []
