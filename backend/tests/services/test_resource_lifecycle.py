"""Tests for resource_lifecycle cascade handlers."""
from unittest.mock import MagicMock, patch
import pytest
import sys
import importlib.util

# Import resource_lifecycle directly to avoid importing models
spec = importlib.util.spec_from_file_location(
    "resource_lifecycle",
    "/Users/edmundhee/Work/GitHub/gruda/bingo-enterprise/bingo/backend/services/resource_lifecycle.py"
)
resource_lifecycle = importlib.util.module_from_spec(spec)
sys.modules["resource_lifecycle"] = resource_lifecycle

# Mock the imports that resource_lifecycle needs
sys.modules['backend.models.pipeline'] = MagicMock()
sys.modules['backend.data_plane.scope'] = MagicMock()
sys.modules['backend.services.data_plane_service'] = MagicMock()

spec.loader.exec_module(resource_lifecycle)

delete_pipeline = resource_lifecycle.delete_pipeline
guard_connection_delete = resource_lifecycle.guard_connection_delete


def _make_pipeline(pipeline_id="p1", target_table="fb_ads", scope_kind="org", scope_id="org1"):
    p = MagicMock()
    p.id = pipeline_id
    p.target_table = target_table
    p.owner_scope_kind = scope_kind
    p.owner_scope_id = scope_id
    p.source_connection_id = 42
    return p


def test_delete_pipeline_drops_table():
    db = MagicMock()
    pipeline = _make_pipeline()
    db.query.return_value.filter.return_value.first.return_value = pipeline

    mock_plane = MagicMock()
    mock_plane.table_exists.return_value = True

    # Mock the imports that delete_pipeline calls
    with patch.dict(sys.modules, {
        'backend.models.pipeline': MagicMock(),
        'backend.data_plane.scope': MagicMock(OwnerScope=MagicMock()),
        'backend.services.data_plane_service': MagicMock(get_default_plane=MagicMock(return_value=mock_plane)),
        'backend.config': MagicMock(settings=MagicMock(redis_url='redis://localhost')),
    }):
        with patch("redis.from_url") as mock_redis:
            mock_redis.return_value = MagicMock()
            delete_pipeline("p1", db)

    mock_plane.drop_table.assert_called_once()
    db.delete.assert_called_once_with(pipeline)


def test_delete_pipeline_not_found_raises():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(LookupError, match="not found"):
        delete_pipeline("nonexistent", db)


def test_guard_connection_delete_no_dependents():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    guard_connection_delete(99, db)  # should not raise


def test_guard_connection_delete_raises_without_cascade():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [_make_pipeline()]

    with pytest.raises(RuntimeError, match="cascade"):
        guard_connection_delete(42, db, cascade=False)


def test_guard_connection_delete_cascades():
    db = MagicMock()
    pipelines = [_make_pipeline("p1"), _make_pipeline("p2")]
    db.query.return_value.filter.return_value.all.return_value = pipelines

    with patch("resource_lifecycle.delete_pipeline") as mock_del:
        guard_connection_delete(42, db, cascade=True)
        assert mock_del.call_count == 2
