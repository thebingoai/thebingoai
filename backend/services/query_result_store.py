"""
Query result store service.

Stores full query results in Redis and delivers them to the frontend
via WebSocket, keeping actual data values out of the LLM context.
"""
import json
import uuid
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_KEY_PREFIX = "query_result"
_DEFAULT_TTL = 3600  # 1 hour


def _redis_key(user_id: str, result_ref: str) -> str:
    return f"{_KEY_PREFIX}:{user_id}:{result_ref}"


def store_query_result(result_ref: str, user_id: str, data: Dict[str, Any], ttl: int = _DEFAULT_TTL) -> None:
    """Store query result in Redis with TTL."""
    import redis as syncredis
    from backend.config import settings

    client = syncredis.from_url(settings.redis_url, decode_responses=True)
    try:
        key = _redis_key(user_id, result_ref)
        client.setex(key, ttl, json.dumps(data))
    finally:
        client.close()


def get_query_result(result_ref: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a cached query result. Returns None if expired or not found."""
    import redis as syncredis
    from backend.config import settings

    client = syncredis.from_url(settings.redis_url, decode_responses=True)
    try:
        raw = client.get(_redis_key(user_id, result_ref))
        if raw is None:
            return None
        return json.loads(raw)
    finally:
        client.close()


def publish_query_result(
    user_id: str, result_ref: str, data: Dict[str, Any], request_id: Optional[str] = None,
) -> None:
    """Push query result to frontend via WebSocket pub/sub.

    Strips SQL fields from the wire payload — the chat UI shows query results,
    not the underlying SQL. Server-side store_query_result keeps the full
    payload (including SQL) for any backend consumer that needs it.

    The channel is per user, not per socket: every tab the user has open gets
    the frame. `request_id` names the chat turn that ran the query so a tab can
    keep only its own; the browser drops frames without one (briefings).
    """
    from backend.services.ws_connection_manager import ConnectionManager

    wire_data = {k: v for k, v in data.items() if k not in ("sql", "sql_queries")}
    message = {
        "type": "query.result",
        "request_id": request_id,
        "result_ref": result_ref,
        "data": wire_data,
    }
    try:
        ConnectionManager.publish_to_user_sync(user_id, message)
    except Exception as e:
        logger.warning(f"Failed to publish query result via WebSocket: {e}")
