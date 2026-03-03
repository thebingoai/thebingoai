"""WebSocket connection manager with Redis Pub/Sub for multi-worker support."""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Redis Pub/Sub channel prefix
_CHANNEL_PREFIX = "ws:user:"


class ConnectionManager:
    """
    Tracks active WebSocket connections per user_id.
    Supports multiple tabs (multiple WebSockets per user).
    Uses Redis Pub/Sub so that any backend worker can push messages to a user.
    """

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    def connect(self, user_id: str, ws: WebSocket) -> None:
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(ws)
        logger.info(f"WS connected: user={user_id} total_tabs={len(self._connections[user_id])}")

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        if user_id in self._connections:
            self._connections[user_id].discard(ws)
            if not self._connections[user_id]:
                del self._connections[user_id]
        logger.info(f"WS disconnected: user={user_id}")

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all connected tabs for a user."""
        connections = self._connections.get(user_id, set())
        if not connections:
            return
        data = json.dumps(message)
        dead: Set[WebSocket] = set()
        for ws in list(connections):
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def listen_redis(self, user_id: str, ws: WebSocket) -> None:
        """
        Subscribe to the user's Redis channel and forward messages to this WebSocket.
        Runs as a background task per connection.
        """
        import redis.asyncio as aioredis
        from backend.config import settings

        channel = f"{_CHANNEL_PREFIX}{user_id}"
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw in pubsub.listen():
                if raw["type"] != "message":
                    continue
                try:
                    payload = json.loads(raw["data"])
                    await ws.send_text(json.dumps(payload))
                except Exception as e:
                    logger.debug(f"Redis→WS forward error: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await redis_client.aclose()

    @staticmethod
    def publish_to_user_sync(user_id: str, message: dict) -> None:
        """
        Synchronous Redis publish for use in Celery workers.
        Publishes to the user's Pub/Sub channel so all connected WebSocket
        listeners (across any worker/process) receive the message.
        """
        import redis as syncredis
        from backend.config import settings

        channel = f"{_CHANNEL_PREFIX}{user_id}"
        client = syncredis.from_url(settings.redis_url, decode_responses=True)
        try:
            client.publish(channel, json.dumps(message))
        finally:
            client.close()


# Module-level singleton
manager = ConnectionManager()
