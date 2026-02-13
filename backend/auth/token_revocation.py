"""JWT token revocation via Redis blacklist."""

import redis
from backend.config import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Redis client for token blacklist (uses DB 0 - same as job store)
_redis_client = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def revoke_token(token: str, expires_in_minutes: int = None) -> None:
    """
    Add token to blacklist.

    Args:
        token: JWT token string
        expires_in_minutes: How long to blacklist (defaults to JWT expiration time)
    """
    if expires_in_minutes is None:
        expires_in_minutes = settings.jwt_expiration_minutes

    client = get_redis_client()
    key = f"revoked_token:{token}"

    # Set with expiration matching JWT lifetime
    # After expiration, the token would have expired anyway
    client.setex(
        key,
        timedelta(minutes=expires_in_minutes),
        "1"
    )

    logger.info(f"Token revoked (expires in {expires_in_minutes} minutes)")


def is_token_revoked(token: str) -> bool:
    """
    Check if token is blacklisted.

    Args:
        token: JWT token string

    Returns:
        True if token is revoked, False otherwise
    """
    client = get_redis_client()
    key = f"revoked_token:{token}"
    return client.exists(key) > 0
