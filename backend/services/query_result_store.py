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


def publish_query_result(user_id: str, result_ref: str, data: Dict[str, Any]) -> None:
    """Push query result to frontend via WebSocket pub/sub."""
    from backend.services.ws_connection_manager import ConnectionManager

    message = {
        "type": "query.result",
        "result_ref": result_ref,
        "data": data,
    }
    try:
        ConnectionManager.publish_to_user_sync(user_id, message)
    except Exception as e:
        logger.warning(f"Failed to publish query result via WebSocket: {e}")
