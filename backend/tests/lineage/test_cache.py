"""Lineage cache tests — TTL set + get, invalidate, pub/sub key wiring."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_cache_key_format():
    from backend.lineage import cache
    assert cache.cache_key("user", "u-1") == "lineage:graph:user:u-1"
    assert cache.cache_key("org", "org-uuid") == "lineage:graph:org:org-uuid"


def test_set_and_get_roundtrip():
    from backend.lineage import cache

    fake = MagicMock()
    fake.setex = MagicMock()
    fake.get = MagicMock(return_value=json.dumps({"scope_kind": "user", "scope_id": "u1", "nodes": []}))
    with patch("backend.lineage.cache._client", return_value=fake):
        cache.set_cached("user", "u1", {"scope_kind": "user", "scope_id": "u1", "nodes": []})
        out = cache.get_cached("user", "u1")
    assert out is not None
    assert out["scope_id"] == "u1"
    fake.setex.assert_called_once()


def test_get_returns_none_when_missing():
    from backend.lineage import cache

    fake = MagicMock()
    fake.get = MagicMock(return_value=None)
    with patch("backend.lineage.cache._client", return_value=fake):
        assert cache.get_cached("user", "u1") is None


def test_invalidate_calls_delete():
    from backend.lineage import cache

    fake = MagicMock()
    with patch("backend.lineage.cache._client", return_value=fake):
        cache.invalidate("user", "u1")
    fake.delete.assert_called_once_with("lineage:graph:user:u1")


def test_publish_invalidation_payload():
    from backend.lineage import cache

    fake = MagicMock()
    with patch("backend.lineage.cache._client", return_value=fake):
        cache.publish_invalidation("user", "u1", source="manual")
    args, _ = fake.publish.call_args
    assert args[0] == cache.LINEAGE_INVALIDATE_CHANNEL
    payload = json.loads(args[1])
    assert payload == {"scope_kind": "user", "scope_id": "u1", "source": "manual"}


def test_subscriber_idempotent_start():
    from backend.lineage import cache

    fake_thread = MagicMock()
    fake_thread.is_alive.return_value = True
    cache._listener_thread = fake_thread
    try:
        # Should not start a new thread when one is already running
        with patch("threading.Thread") as mock_thread:
            cache.start_subscriber()
            mock_thread.assert_not_called()
    finally:
        cache._listener_thread = None


def test_ttl_constant_is_five_minutes():
    from backend.lineage import cache
    assert cache.LINEAGE_TTL_SECONDS == 300
