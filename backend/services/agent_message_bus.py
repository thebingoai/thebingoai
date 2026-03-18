"""
User-scoped message routing for the agent mesh.

Dual-write pattern:
- PostgreSQL for durable history
- Redis for fast delivery (RPUSH to inbox, Pub/Sub notifications)

All operations validate that both sender and receiver belong to the same user.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

import redis

from backend.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds


def _get_redis() -> redis.Redis:
    return redis.from_url(settings.agent_mesh_redis_url, decode_responses=True)


class AgentMessageBus:
    """Send, receive, and route messages between user-scoped agent sessions."""

    def __init__(
        self,
        db_session=None,
        redis_client: Optional[redis.Redis] = None,
    ):
        self.db = db_session
        self.redis = redis_client or _get_redis()

    def send(
        self,
        user_id: str,
        from_session_id: str,
        to_session_id: str,
        content: dict,
        message_type: str = "request",
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        Send a message between two sessions owned by the same user.

        Args:
            user_id: Owner user ID (both sessions must belong to this user)
            from_session_id: Sender session ID
            to_session_id: Receiver session ID
            content: Message payload (JSON-serializable dict)
            message_type: request/response/notification/broadcast
            correlation_id: Optional correlation ID for request/response pairing

        Returns:
            Message ID

        Raises:
            PermissionError: If sessions don't belong to the same user
        """
        # Validate both sessions belong to user
        self._validate_user_owns_sessions(user_id, from_session_id, to_session_id)

        msg_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        now = datetime.utcnow()

        # 1. Write to PostgreSQL (durable history)
        if self.db:
            from backend.models.agent_message import AgentMessage

            db_msg = AgentMessage(
                id=msg_id,
                user_id=user_id,
                from_session_id=from_session_id,
                to_session_id=to_session_id,
                message_type=message_type,
                content=content,
                correlation_id=correlation_id,
                status="pending",
                created_at=now,
            )
            self.db.add(db_msg)
            self.db.commit()

        # 2. Push to Redis inbox (fast delivery)
        envelope = json.dumps({
            "id": msg_id,
            "from_session_id": from_session_id,
            "to_session_id": to_session_id,
            "user_id": user_id,
            "message_type": message_type,
            "content": content,
            "correlation_id": correlation_id,
            "created_at": now.isoformat(),
        })
        self.redis.rpush(f"agent:inbox:{to_session_id}", envelope)

        # 3. Publish notification (wake target agent)
        self.redis.publish(f"agent:notify:{to_session_id}", envelope)

        logger.debug(
            "Message %s: %s -> %s (type=%s, corr=%s)",
            msg_id, from_session_id, to_session_id, message_type, correlation_id,
        )
        return msg_id

    def send_and_wait(
        self,
        user_id: str,
        from_session_id: str,
        to_session_id: str,
        content: dict,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Optional[dict]:
        """
        Send a request and block until the target agent responds.

        Uses Redis Pub/Sub on a correlation-specific channel.

        Args:
            user_id: Owner user ID
            from_session_id: Sender session ID
            to_session_id: Receiver session ID
            content: Request payload
            timeout: Max seconds to wait (default 120)

        Returns:
            Response content dict, or None on timeout
        """
        correlation_id = str(uuid.uuid4())

        # Subscribe BEFORE sending to avoid race condition
        pubsub = self.redis.pubsub()
        response_channel = f"agent:response:{correlation_id}"
        pubsub.subscribe(response_channel)

        try:
            # Send the request
            self.send(
                user_id=user_id,
                from_session_id=from_session_id,
                to_session_id=to_session_id,
                content=content,
                message_type="request",
                correlation_id=correlation_id,
            )

            # Block for response
            message = pubsub.get_message(timeout=timeout)
            # First message is the subscription confirmation
            while message and message.get("type") == "subscribe":
                message = pubsub.get_message(timeout=timeout)

            if message and message.get("type") == "message":
                return json.loads(message["data"])

            logger.warning(
                "Timeout waiting for response (corr=%s, timeout=%ds)",
                correlation_id, timeout,
            )
            return None

        finally:
            pubsub.unsubscribe(response_channel)
            pubsub.close()

    def respond(
        self,
        user_id: str,
        from_session_id: str,
        to_session_id: str,
        content: dict,
        correlation_id: str,
    ) -> str:
        """
        Send a response to a previous request, publishing on the correlation channel.
        """
        msg_id = self.send(
            user_id=user_id,
            from_session_id=from_session_id,
            to_session_id=to_session_id,
            content=content,
            message_type="response",
            correlation_id=correlation_id,
        )

        # Also publish on the response channel for send_and_wait listeners
        self.redis.publish(
            f"agent:response:{correlation_id}",
            json.dumps(content),
        )
        return msg_id

    def drain_inbox(self, user_id: str, session_id: str) -> List[dict]:
        """
        Pop all pending messages from a session's inbox.

        Args:
            user_id: Owner user ID (for ownership validation)
            session_id: Session whose inbox to drain

        Returns:
            List of message envelopes

        Raises:
            PermissionError: If session doesn't belong to user
        """
        # Validate ownership
        if not self.redis.sismember(f"agent:user_sessions:{user_id}", session_id):
            raise PermissionError(
                f"Session {session_id} is not owned by user {user_id}"
            )

        messages = []
        inbox_key = f"agent:inbox:{session_id}"
        while True:
            raw = self.redis.lpop(inbox_key)
            if raw is None:
                break
            messages.append(json.loads(raw))

        # Update status in Postgres if we have a DB session
        if self.db and messages:
            from backend.models.agent_message import AgentMessage

            msg_ids = [m["id"] for m in messages if "id" in m]
            if msg_ids:
                self.db.query(AgentMessage).filter(
                    AgentMessage.id.in_(msg_ids),
                    AgentMessage.user_id == user_id,
                ).update({"status": "delivered"}, synchronize_session=False)
                self.db.commit()

        return messages

    def broadcast(
        self,
        user_id: str,
        from_session_id: str,
        content: dict,
        filter_type: Optional[str] = None,
    ) -> List[str]:
        """
        Send a message to all of a user's agents (except the sender).

        Args:
            user_id: Owner user ID
            from_session_id: Sender (excluded from broadcast)
            content: Message payload
            filter_type: Optional agent_type filter

        Returns:
            List of message IDs sent
        """
        session_ids = self.redis.smembers(f"agent:user_sessions:{user_id}")
        msg_ids = []

        for sid in session_ids:
            if sid == from_session_id:
                continue

            if filter_type:
                session_data = self.redis.hgetall(f"agent:session:{sid}")
                if session_data.get("agent_type") != filter_type:
                    continue

            try:
                msg_id = self.send(
                    user_id=user_id,
                    from_session_id=from_session_id,
                    to_session_id=sid,
                    content=content,
                    message_type="broadcast",
                )
                msg_ids.append(msg_id)
            except Exception as e:
                logger.warning("Broadcast to %s failed: %s", sid, e)

        return msg_ids

    def get_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 20,
    ) -> List[dict]:
        """
        Get message history for a session from PostgreSQL.

        Args:
            user_id: Owner user ID
            session_id: Session ID to get history for
            limit: Max messages to return

        Returns:
            List of message dicts ordered by created_at
        """
        if not self.db:
            return []

        from backend.models.agent_message import AgentMessage

        messages = (
            self.db.query(AgentMessage)
            .filter(
                AgentMessage.user_id == user_id,
                (AgentMessage.from_session_id == session_id)
                | (AgentMessage.to_session_id == session_id),
            )
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": m.id,
                "from_session_id": m.from_session_id,
                "to_session_id": m.to_session_id,
                "message_type": m.message_type,
                "content": m.content,
                "correlation_id": m.correlation_id,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in reversed(messages)
        ]

    def _validate_user_owns_sessions(
        self, user_id: str, *session_ids: str
    ) -> None:
        """Raise PermissionError if any session is not owned by user."""
        user_sessions_key = f"agent:user_sessions:{user_id}"
        for sid in session_ids:
            if not self.redis.sismember(user_sessions_key, sid):
                raise PermissionError(
                    f"Session {sid} is not owned by user {user_id}"
                )
