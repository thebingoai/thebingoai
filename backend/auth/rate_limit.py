"""Rate limiting for authentication endpoints using Redis."""

import redis
from fastapi import Request, HTTPException, status
from backend.config import settings
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Redis client for rate limiting (uses DB 0 - same as job store)
_redis_client = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def check_rate_limit(
    request: Request,
    max_requests: int = 5,
    window_minutes: int = 15
) -> None:
    """
    Rate limit check using sliding window.

    Args:
        request: FastAPI request object
        max_requests: Maximum requests allowed in window
        window_minutes: Time window in minutes

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Use forwarded IP if behind proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    # Rate limit key
    key = f"rate_limit:{request.url.path}:{client_ip}"

    client = get_redis_client()

    # Get current request count
    current = client.get(key)

    if current is None:
        # First request in window
        client.setex(key, timedelta(minutes=window_minutes), "1")
        return

    current_count = int(current)

    if current_count >= max_requests:
        # Rate limit exceeded
        ttl = client.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
            headers={"Retry-After": str(ttl)}
        )

    # Increment counter
    client.incr(key)


# Dependency for authentication endpoints
async def auth_rate_limit(request: Request) -> None:
    """
    Rate limit dependency for auth endpoints.

    5 requests per 15 minutes per IP address.
    """
    await check_rate_limit(request, max_requests=5, window_minutes=15)
