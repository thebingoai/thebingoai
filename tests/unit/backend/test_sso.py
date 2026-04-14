"""Tests for backend.auth.sso — SSO token validation, logout, and config."""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.auth.sso import AuthUser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_key(token: str) -> str:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return f"sso:token:{token_hash}"


def _make_auth_user(**overrides) -> AuthUser:
    defaults = {"id": "user-1", "email": "a@b.com", "is_active": True, "is_verified": True}
    defaults.update(overrides)
    return AuthUser(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_clients():
    """Reset module-level singletons between tests."""
    import backend.auth.sso as sso_mod
    sso_mod._redis_client = None
    sso_mod._http_client = None
    yield
    sso_mod._redis_client = None
    sso_mod._http_client = None


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    return r


@pytest.fixture
def mock_http():
    return AsyncMock(spec=httpx.AsyncClient)


# ---------------------------------------------------------------------------
# validate_token tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_token_cache_hit(mock_redis):
    """validate_token() returns cached AuthUser on Redis cache hit."""
    user = _make_auth_user()
    mock_redis.get = AsyncMock(return_value=user.model_dump_json())

    with patch("backend.auth.sso._get_redis_client", return_value=mock_redis):
        from backend.auth.sso import validate_token
        result = await validate_token("tok123")

    assert result is not None
    assert result.id == "user-1"
    assert result.email == "a@b.com"
    mock_redis.get.assert_awaited_once_with(_cache_key("tok123"))


@pytest.mark.asyncio
async def test_validate_token_cache_miss(mock_redis, mock_http):
    """validate_token() calls SSO /api/v1/auth/me on cache miss, caches result."""
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "u2", "email": "x@y.com", "is_active": True, "is_verified": False}
    response.raise_for_status = MagicMock()
    mock_http.get = AsyncMock(return_value=response)

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = "sk_test"
        mock_settings.sso_token_cache_ttl = 300
        from backend.auth.sso import validate_token
        result = await validate_token("tok456")

    assert result is not None
    assert result.id == "u2"
    assert result.email == "x@y.com"
    mock_http.get.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_token_401(mock_redis, mock_http):
    """validate_token() returns None on 401 from SSO."""
    mock_redis.get = AsyncMock(return_value=None)

    response = MagicMock()
    response.status_code = 401
    mock_http.get = AsyncMock(return_value=response)

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = ""
        from backend.auth.sso import validate_token
        result = await validate_token("bad_tok")

    assert result is None


@pytest.mark.asyncio
async def test_validate_token_no_api_key(mock_redis, mock_http):
    """validate_token() omits X-API-Key when both secret key and publishable key are empty."""
    mock_redis.get = AsyncMock(return_value=None)

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "u1", "email": "a@b.com", "is_active": True, "is_verified": True}
    response.raise_for_status = MagicMock()
    mock_http.get = AsyncMock(return_value=response)
    mock_redis.setex = AsyncMock()

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = ""
        mock_settings.sso_publishable_key = ""
        mock_settings.sso_token_cache_ttl = 300
        from backend.auth.sso import validate_token
        result = await validate_token("tok_no_keys")

    call_kwargs = mock_http.get.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert "X-API-Key" not in headers


@pytest.mark.asyncio
async def test_validate_token_community_app_name(mock_redis, mock_http):
    """validate_token() sends X-API-Key: <app name> when no secret key but publishable key is set (community)."""
    mock_redis.get = AsyncMock(return_value=None)

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "u1", "email": "a@b.com", "is_active": True, "is_verified": True}
    response.raise_for_status = MagicMock()
    mock_http.get = AsyncMock(return_value=response)
    mock_redis.setex = AsyncMock()

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = ""
        mock_settings.sso_publishable_key = "bingo-community"
        mock_settings.sso_token_cache_ttl = 300
        from backend.auth.sso import validate_token
        result = await validate_token("tok_community")

    call_kwargs = mock_http.get.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("X-API-Key") == "bingo-community"


@pytest.mark.asyncio
async def test_validate_token_with_api_key(mock_redis, mock_http):
    """validate_token() includes X-API-Key header using sso_publishable_key."""
    mock_redis.get = AsyncMock(return_value=None)

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"id": "u1", "email": "a@b.com", "is_active": True, "is_verified": True}
    response.raise_for_status = MagicMock()
    mock_http.get = AsyncMock(return_value=response)
    mock_redis.setex = AsyncMock()

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_publishable_key = "pk_test_key"
        mock_settings.sso_token_cache_ttl = 300
        from backend.auth.sso import validate_token
        result = await validate_token("tok_enterprise")

    call_kwargs = mock_http.get.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("X-API-Key") == "pk_test_key"


# ---------------------------------------------------------------------------
# logout tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_success(mock_redis, mock_http):
    """logout() deletes Redis cache and calls SSO /api/v1/auth/logout."""
    mock_redis.delete = AsyncMock()

    response = MagicMock()
    response.status_code = 200
    mock_http.post = AsyncMock(return_value=response)

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = "sk_test"
        from backend.auth.sso import logout
        result = await logout("access_tok", "refresh_tok")

    assert result is True
    mock_redis.delete.assert_awaited_once_with(_cache_key("access_tok"))
    mock_http.post.assert_awaited_once()
    call_kwargs = mock_http.post.call_args
    assert call_kwargs.kwargs.get("json") == {"refresh_token": "refresh_tok"}


@pytest.mark.asyncio
async def test_logout_no_api_key(mock_redis, mock_http):
    """logout() omits X-API-Key when both secret key and publishable key are empty."""
    mock_redis.delete = AsyncMock()

    response = MagicMock()
    response.status_code = 204
    mock_http.post = AsyncMock(return_value=response)

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = ""
        mock_settings.sso_publishable_key = ""
        from backend.auth.sso import logout
        result = await logout("access_tok", "refresh_tok")

    assert result is True
    call_kwargs = mock_http.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert "X-API-Key" not in headers


@pytest.mark.asyncio
async def test_logout_community_app_name(mock_redis, mock_http):
    """logout() sends X-API-Key: <app name> when no secret key but publishable key is set (community)."""
    mock_redis.delete = AsyncMock()

    response = MagicMock()
    response.status_code = 200
    mock_http.post = AsyncMock(return_value=response)

    with (
        patch("backend.auth.sso._get_redis_client", return_value=mock_redis),
        patch("backend.auth.sso._get_http_client", return_value=mock_http),
        patch("backend.auth.sso.settings") as mock_settings,
    ):
        mock_settings.sso_secret_key = ""
        mock_settings.sso_publishable_key = "bingo-community"
        from backend.auth.sso import logout
        result = await logout("access_tok", "refresh_tok")

    assert result is True
    call_kwargs = mock_http.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("X-API-Key") == "bingo-community"


# ---------------------------------------------------------------------------
# get_config tests
# ---------------------------------------------------------------------------

def test_get_config_no_key():
    """get_config() returns only provider and sso_base_url when publishable key is empty."""
    with patch("backend.auth.sso.settings") as mock_settings:
        mock_settings.sso_base_url = "https://sso.example.com"
        mock_settings.sso_publishable_key = ""
        from backend.auth.sso import get_config
        config = get_config()

    assert config == {"provider": "sso", "sso_base_url": "https://sso.example.com"}
    assert "publishable_key" not in config
    assert "google_oauth_url" not in config


def test_get_config_community():
    """get_config() returns publishable_key (app name) but no google_oauth_url for community."""
    with patch("backend.auth.sso.settings") as mock_settings:
        mock_settings.sso_base_url = "https://sso.thelead.io"
        mock_settings.sso_publishable_key = "bingo-community"
        from backend.auth.sso import get_config
        config = get_config()

    assert config["provider"] == "sso"
    assert config["sso_base_url"] == "https://sso.thelead.io"
    assert config["publishable_key"] == "bingo-community"
    assert "google_oauth_url" not in config


def test_get_config_enterprise():
    """get_config() returns publishable_key and google_oauth_url when key is set (enterprise)."""
    with patch("backend.auth.sso.settings") as mock_settings:
        mock_settings.sso_base_url = "https://sso.thelead.io"
        mock_settings.sso_publishable_key = "pk_live_abc123"
        from backend.auth.sso import get_config
        config = get_config()

    assert config["provider"] == "sso"
    assert config["sso_base_url"] == "https://sso.thelead.io"
    assert config["publishable_key"] == "pk_live_abc123"
    assert config["google_oauth_url"] == "https://sso.thelead.io/api/v1/oauth/google"
