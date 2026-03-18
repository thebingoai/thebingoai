"""
Redis-backed agent session registry (DB 4).

All operations are user-scoped — sessions are owned by the user who creates them.
TTL-based cleanup: 5 min without heartbeat = expired.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import redis

from backend.config import settings

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 300  # 5 minutes without heartbeat = expired


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.agent_mesh_redis_url, decode_responses=True)


class AgentRegistry:
    """Register, deregister, and heartbeat agent sessions in Redis."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or _get_redis()

    def register_session(
        self,
        user_id: str,
        session_id: str,
        agent_type: str,
        capabilities: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Register an agent session for a user."""
        now = datetime.utcnow().isoformat()
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_type": agent_type,
            "status": "active",
            "capabilities": json.dumps(capabilities or {}),
            "metadata": json.dumps(metadata or {}),
            "last_heartbeat": now,
            "registered_at": now,
        }

        pipe = self.redis.pipeline()
        pipe.hset(f"agent:session:{session_id}", mapping=session_data)
        pipe.expire(f"agent:session:{session_id}", SESSION_TTL_SECONDS)
        pipe.sadd(f"agent:user_sessions:{user_id}", session_id)
        pipe.execute()

        logger.info(
            "Registered agent session %s (type=%s) for user %s",
            session_id, agent_type, user_id,
        )
        return session_data

    def deregister_session(self, user_id: str, session_id: str) -> None:
        """Remove an agent session. Raises PermissionError if wrong user."""
        self._validate_ownership(user_id, session_id)

        pipe = self.redis.pipeline()
        pipe.delete(f"agent:session:{session_id}")
        pipe.srem(f"agent:user_sessions:{user_id}", session_id)
        # Clean up inbox and notify channels
        pipe.delete(f"agent:inbox:{session_id}")
        pipe.execute()

        logger.info("Deregistered agent session %s for user %s", session_id, user_id)

    def heartbeat(self, session_id: str) -> bool:
        """Update heartbeat timestamp. Returns False if session doesn't exist."""
        key = f"agent:session:{session_id}"
        if not self.redis.exists(key):
            return False

        pipe = self.redis.pipeline()
        pipe.hset(key, "last_heartbeat", datetime.utcnow().isoformat())
        pipe.hset(key, "status", "active")
        pipe.expire(key, SESSION_TTL_SECONDS)
        pipe.execute()
        return True

    def update_status(self, session_id: str, status: str) -> None:
        """Update session status (active/idle/terminated)."""
        key = f"agent:session:{session_id}"
        if self.redis.exists(key):
            self.redis.hset(key, "status", status)

    def get_session(self, session_id: str) -> Optional[dict]:
        """Get raw session data from Redis."""
        data = self.redis.hgetall(f"agent:session:{session_id}")
        if not data:
            return None
        data["capabilities"] = json.loads(data.get("capabilities", "{}"))
        data["metadata"] = json.loads(data.get("metadata", "{}"))
        return data

    def get_user_session_ids(self, user_id: str) -> set:
        """Get all session IDs for a user."""
        return self.redis.smembers(f"agent:user_sessions:{user_id}")

    def cleanup_stale_sessions(self) -> int:
        """
        Mark sessions that have exceeded TTL as degraded.
        Called by the agent_health_check periodic task.
        Returns the number of sessions marked stale.
        """
        # Scan for all session keys
        stale_count = 0
        cursor = 0
        while True:
            cursor, keys = self.redis.scan(cursor, match="agent:session:*", count=100)
            for key in keys:
                data = self.redis.hgetall(key)
                if not data:
                    continue
                last_hb = data.get("last_heartbeat")
                if not last_hb:
                    continue
                try:
                    last_hb_dt = datetime.fromisoformat(last_hb)
                except (ValueError, TypeError):
                    continue
                if datetime.utcnow() - last_hb_dt > timedelta(seconds=SESSION_TTL_SECONDS):
                    if data.get("status") != "terminated":
                        self.redis.hset(key, "status", "degraded")
                        stale_count += 1
            if cursor == 0:
                break
        return stale_count

    def _validate_ownership(self, user_id: str, session_id: str) -> None:
        """Raise PermissionError if session is not owned by user."""
        if not self.redis.sismember(f"agent:user_sessions:{user_id}", session_id):
            raise PermissionError(
                f"Session {session_id} is not owned by user {user_id}"
            )
