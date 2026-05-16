"""Shared primitives for the user-scoped agent mesh.

The mesh registry, discovery and message-bus services were each carrying their
own copy of the Redis client factory and of the session-ownership guard, so
e.g. tightening the guard required three coordinated edits. This module is the
single source of truth for both.
"""

from __future__ import annotations

import redis

from backend.config import settings


def get_redis() -> redis.Redis:
    """Return a Redis client pointed at the agent-mesh DB.

    ``decode_responses=True`` so callers get ``str`` back instead of ``bytes``.
    """
    return redis.from_url(settings.agent_mesh_redis_url, decode_responses=True)


def assert_session_owned(
    redis_client: redis.Redis, user_id: str, session_id: str
) -> None:
    """Raise ``PermissionError`` if the session is not owned by ``user_id``.

    Mesh sessions live in the user-scoped set ``agent:user_sessions:<user_id>``.
    """
    if not redis_client.sismember(f"agent:user_sessions:{user_id}", session_id):
        raise PermissionError(
            f"Session {session_id} is not owned by user {user_id}"
        )
