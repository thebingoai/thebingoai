"""
User-scoped agent session discovery.

All lookups filter by user_id — agents can only discover other agents
belonging to the same user.
"""

import logging
from typing import List, Optional

import redis

from backend.config import settings
from backend.services.agent_registry import AgentRegistry

logger = logging.getLogger(__name__)


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.agent_mesh_redis_url, decode_responses=True)


class AgentDiscovery:
    """Discover active agent sessions for a specific user."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or _get_redis()
        self._registry = AgentRegistry(redis_client=self.redis)

    def list_sessions(
        self, user_id: str, filter_type: Optional[str] = None
    ) -> List[dict]:
        """
        List active agent sessions for a user.

        Args:
            user_id: Owner user ID
            filter_type: Optional agent_type filter (e.g. "data_agent")

        Returns:
            List of session dicts with id, agent_type, status, capabilities
        """
        session_ids = self._registry.get_user_session_ids(user_id)
        sessions = []
        for sid in session_ids:
            data = self._registry.get_session(sid)
            if not data:
                continue
            if data.get("status") == "terminated":
                continue
            if filter_type and data.get("agent_type") != filter_type:
                continue
            sessions.append(data)
        return sessions

    def get_session(self, user_id: str, session_id: str) -> dict:
        """
        Get a specific session, validating user ownership.

        Raises:
            PermissionError: If session is not owned by user
            ValueError: If session not found
        """
        if not self.redis.sismember(f"agent:user_sessions:{user_id}", session_id):
            raise PermissionError(
                f"Session {session_id} is not owned by user {user_id}"
            )

        data = self._registry.get_session(session_id)
        if not data:
            raise ValueError(f"Session {session_id} not found")
        return data

    def find_session_by_type(
        self, user_id: str, agent_type: str
    ) -> Optional[dict]:
        """
        Find the first active session of a given type for a user.

        Returns:
            Session dict or None if no matching session found
        """
        sessions = self.list_sessions(user_id, filter_type=agent_type)
        if sessions:
            # Prefer active over idle
            active = [s for s in sessions if s.get("status") == "active"]
            return active[0] if active else sessions[0]
        return None
