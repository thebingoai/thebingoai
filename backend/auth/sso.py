"""SSO authentication module — validates tokens against LEAD SSO service."""

import hashlib
import logging
from typing import Optional

import httpx
import redis.asyncio as aioredis
from pydantic import BaseModel

from backend.config import settings


class AuthUser(BaseModel):
    """Normalized user data from SSO authentication."""
    id: str
    email: str
    is_active: bool = True
    is_verified: bool = False

logger = logging.getLogger(__name__)

# Module-level clients (reused across requests)
_redis_client: Optional[aioredis.Redis] = None
_http_client: Optional[httpx.AsyncClient] = None


def _get_redis_client() -> aioredis.Redis:
    """Get or create async Redis client (DB 3, dedicated for SSO cache)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.sso_redis_url, decode_responses=True)
    return _redis_client


def _get_http_client() -> httpx.AsyncClient:
    """Get or create async HTTP client for SSO API calls."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(base_url=settings.sso_base_url, timeout=10.0)
    return _http_client


def _cache_key(token: str) -> str:
    """Generate Redis cache key for a token (sha256 hash to keep key short)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return f"sso:token:{token_hash}"


async def validate_token(access_token: str) -> Optional[AuthUser]:
    """
    Validate SSO access token and return AuthUser.

    Flow:
    1. Check Redis cache (sso:token:<sha256(token)>)
    2. Cache miss -> call GET /api/v1/auth/me with Bearer token
    3. Cache result with TTL from settings
    4. Return AuthUser or None on 401/error

    X-API-Key header is only included when sso_secret_key is configured (enterprise).
    """
    redis = _get_redis_client()
    cache_key = _cache_key(access_token)

    # Check cache first
    cached = await redis.get(cache_key)
    if cached:
        try:
            return AuthUser.model_validate_json(cached)
        except Exception:
            await redis.delete(cache_key)

    # Call SSO /me endpoint
    try:
        client = _get_http_client()
        headers = {"Authorization": f"Bearer {access_token}"}
        # X-API-Key: uses sso_secret_key (enterprise) or sso_publishable_key/app name (community)
        if settings.sso_secret_key:
            headers["X-API-Key"] = settings.sso_secret_key
        elif settings.sso_publishable_key:
            headers["X-API-Key"] = settings.sso_publishable_key

        response = await client.get("/api/v1/auth/me", headers=headers)

        if response.status_code == 401:
            return None

        response.raise_for_status()
        data = response.json()

        auth_user = AuthUser(
            id=str(data["id"]),
            email=data["email"],
            is_active=data.get("is_active", False),
            is_verified=data.get("is_verified", False),
        )

        # Cache the result
        await redis.setex(
            cache_key,
            settings.sso_token_cache_ttl,
            auth_user.model_dump_json(),
        )

        return auth_user

    except httpx.HTTPStatusError as e:
        logger.warning(f"SSO token validation failed: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"SSO token validation error: {e}")
        return None


async def logout(access_token: str, refresh_token: str) -> bool:
    """
    Invalidate token cache and blacklist refresh token on SSO.

    X-API-Key header is only included when sso_secret_key is configured (enterprise).
    """
    redis = _get_redis_client()

    # Invalidate cache
    cache_key = _cache_key(access_token)
    await redis.delete(cache_key)

    # Tell SSO to blacklist the refresh token
    try:
        client = _get_http_client()
        # X-API-Key: uses sso_secret_key (enterprise) or sso_publishable_key/app name (community)
        headers = {}
        if settings.sso_secret_key:
            headers["X-API-Key"] = settings.sso_secret_key
        elif settings.sso_publishable_key:
            headers["X-API-Key"] = settings.sso_publishable_key

        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers=headers,
        )
        return response.status_code in (200, 204)
    except Exception as e:
        logger.error(f"SSO logout error: {e}")
        return False


def get_config() -> dict:
    """
    Return SSO config for the frontend.

    Community mode (app name key): returns provider, sso_base_url, and publishable_key — no Google OAuth.
    Enterprise mode (publishable key set): also includes publishable_key and google_oauth_url.
    """
    config = {
        "provider": "sso",
        "sso_base_url": settings.sso_base_url,
    }
    if settings.sso_publishable_key:
        config["publishable_key"] = settings.sso_publishable_key
        if settings.sso_publishable_key.startswith("pk_"):
            config["google_oauth_url"] = f"{settings.sso_base_url}/api/v1/oauth/google"
    return config
