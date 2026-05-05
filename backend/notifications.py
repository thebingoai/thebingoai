"""Lightweight Redis-backed notification event bus.

Publishers: publish(event_dict)
Subscribers: subscribe(event_type, handler_fn)  — called on plugin on_startup

Events are delivered in-process via a background thread that listens on a
single Redis Pub/Sub channel "bingo:notifications". Subscriber handlers are
called synchronously in the listener thread; keep them fast (async dispatch
to Celery is the recommended pattern for slow work).
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

_CHANNEL = "bingo:notifications"
_subscribers: dict[str, list[Callable]] = {}
_listener_started = False
_listener_lock = threading.Lock()


def subscribe(event_type: str, handler: Callable[[dict], None]) -> None:
    """Register *handler* for *event_type*. Called once per plugin on_startup."""
    _subscribers.setdefault(event_type, []).append(handler)
    _ensure_listener()


def publish(event: dict) -> None:
    """Publish an event dict onto the notification channel. Fire-and-forget."""
    try:
        _get_redis().publish(_CHANNEL, json.dumps(event))
    except Exception:
        logger.exception("notifications.publish failed for event_type=%s", event.get("event_type"))


def _ensure_listener() -> None:
    global _listener_started
    with _listener_lock:
        if _listener_started:
            return
        _listener_started = True
        t = threading.Thread(target=_listen, daemon=True, name="bingo-notifications-listener")
        t.start()


def _listen() -> None:
    import time
    while True:
        try:
            r = _get_redis()
            ps = r.pubsub()
            ps.subscribe(_CHANNEL)
            logger.info("notifications: listener subscribed to %s", _CHANNEL)
            for msg in ps.listen():
                if msg["type"] != "message":
                    continue
                try:
                    event = json.loads(msg["data"])
                except Exception:
                    continue
                _dispatch(event)
        except Exception:
            logger.exception("notifications: listener error, reconnecting in 5s")
            time.sleep(5)


def _dispatch(event: dict) -> None:
    etype = event.get("event_type")
    if not etype:
        return
    for handler in _subscribers.get(etype, []):
        try:
            handler(event)
        except Exception:
            logger.exception("notifications: handler %s raised for event_type=%s", handler, etype)


def _get_redis():
    import redis
    from backend.config import settings
    return redis.from_url(settings.redis_url, decode_responses=True)
