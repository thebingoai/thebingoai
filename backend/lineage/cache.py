"""Lineage Redis cache + pub/sub invalidation (Phase 6 P6.1).

The lineage graph is derived; we cache the rendered JSON for 5 minutes per
scope to keep repeated views fast. Cache entries are deleted when:

* the Pipeline runner publishes ``lineage:invalidate`` after a successful run
  (see ``backend/pipelines/runner.py``), or
* the dbt runner publishes ``lineage:invalidate`` after a successful run
  (see ``backend/transforms/runner.py``), or
* a resource lifecycle delete publishes ``lineage:invalidate``
  (see ``backend/services/resource_lifecycle.py``), or
* a dashboard widget edit publishes ``lineage:invalidate``.

The 5-minute TTL is a belt-and-braces safety net for missed messages.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Optional

import redis as syncredis

from backend.config import settings

logger = logging.getLogger(__name__)

LINEAGE_TTL_SECONDS = 5 * 60
LINEAGE_INVALIDATE_CHANNEL = "lineage:invalidate"


def _client() -> syncredis.Redis:
    return syncredis.from_url(settings.redis_url, decode_responses=True)


def cache_key(scope_kind: str, scope_id: str) -> str:
    return f"lineage:graph:{scope_kind}:{scope_id}"


def get_cached(scope_kind: str, scope_id: str) -> Optional[dict]:
    try:
        raw = _client().get(cache_key(scope_kind, scope_id))
    except Exception:
        logger.warning("lineage cache: GET failed", exc_info=True)
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def set_cached(scope_kind: str, scope_id: str, payload: dict) -> None:
    try:
        _client().setex(
            cache_key(scope_kind, scope_id),
            LINEAGE_TTL_SECONDS,
            json.dumps(payload),
        )
    except Exception:
        logger.warning("lineage cache: SETEX failed", exc_info=True)


def invalidate(scope_kind: str, scope_id: str) -> None:
    try:
        _client().delete(cache_key(scope_kind, scope_id))
    except Exception:
        logger.warning("lineage cache: DELETE failed", exc_info=True)


def publish_invalidation(scope_kind: str, scope_id: str, **extra) -> None:
    """Publish a lineage:invalidate message — call this from dashboard-widget edits."""
    try:
        _client().publish(
            LINEAGE_INVALIDATE_CHANNEL,
            json.dumps({"scope_kind": scope_kind, "scope_id": scope_id, **extra}),
        )
    except Exception:
        logger.warning("lineage cache: publish failed", exc_info=True)


# ---------------------------------------------------------------------------
# Pub/sub subscriber (started by app on_startup)
# ---------------------------------------------------------------------------

_listener_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def _listen_loop() -> None:
    """Subscribe to lineage:invalidate and DEL the matching cache key."""
    while not _stop_event.is_set():
        try:
            ps = _client().pubsub()
            ps.subscribe(LINEAGE_INVALIDATE_CHANNEL)
            for message in ps.listen():
                if _stop_event.is_set():
                    break
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                try:
                    payload = json.loads(data) if isinstance(data, str) else {}
                except Exception:
                    continue
                scope_kind = payload.get("scope_kind")
                scope_id = payload.get("scope_id")
                if scope_kind and scope_id:
                    invalidate(scope_kind, scope_id)
                    logger.info("lineage cache invalidated for %s/%s", scope_kind, scope_id)
        except Exception:
            if _stop_event.is_set():
                return
            logger.warning("lineage cache: pub/sub loop crashed; reconnecting", exc_info=True)
            _stop_event.wait(2.0)


def start_subscriber() -> None:
    """Start the lineage invalidation subscriber in a daemon thread (idempotent)."""
    global _listener_thread
    if _listener_thread and _listener_thread.is_alive():
        return
    _stop_event.clear()
    t = threading.Thread(target=_listen_loop, name="lineage-invalidate-subscriber", daemon=True)
    t.start()
    _listener_thread = t


def stop_subscriber() -> None:
    _stop_event.set()
