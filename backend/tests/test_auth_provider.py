"""Tests for the auth provider abstraction layer."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.auth.base import AuthUser, BaseAuthProvider
from backend.auth.providers.sso_provider import SSOAuthProvider


class TestAuthProviderFactory:
    """Test factory returns correct provider based on config."""

    def test_get_auth_provider_returns_sso(self):
        from backend.auth.factory import get_auth_provider
        provider = get_auth_provider()
        assert isinstance(provider, SSOAuthProvider)
        assert provider.name == "sso"

    def test_get_auth_provider_unknown_raises(self):
        from backend.auth.factory import get_auth_provider
        with patch("backend.auth.factory.settings") as mock_settings:
            mock_settings.auth_provider = "nonexistent"
            with pytest.raises(ValueError, match="Unknown auth provider 'nonexistent'"):
                get_auth_provider()


class TestSSOAuthProvider:
    """Test SSO provider validate_token and logout."""

    @pytest.fixture
    def provider(self):
        return SSOAuthProvider()

    def test_name(self, provider):
        assert provider.name == "sso"

    @pytest.mark.asyncio
    async def test_validate_token_cache_hit(self, provider):
        """When token is cached in Redis, return cached AuthUser."""
        cached_user = AuthUser(id="u1", email="test@example.com", is_active=True, is_verified=True)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = cached_user.model_dump_json()

        with patch("backend.auth.providers.sso_provider._get_redis_client", return_value=mock_redis):
            result = await provider.validate_token("test-token")

        assert result is not None
        assert result.id == "u1"
        assert result.email == "test@example.com"
        assert result.is_active is True
        assert result.is_verified is True

    @pytest.mark.asyncio
    async def test_validate_token_cache_miss_http_success(self, provider):
        """When token not cached, call SSO HTTP endpoint and cache result."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "id": "u2",
            "email": "user@example.com",
            "is_active": True,
            "is_verified": True,
        }

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response

        with (
            patch("backend.auth.providers.sso_provider._get_redis_client", return_value=mock_redis),
            patch("backend.auth.providers.sso_provider._get_http_client", return_value=mock_http),
        ):
            result = await provider.validate_token("test-token")

        assert result is not None
        assert result.id == "u2"
        assert result.email == "user@example.com"
        mock_redis.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_token_401_returns_none(self, provider):
        """When SSO returns 401, return None."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response

        with (
            patch("backend.auth.providers.sso_provider._get_redis_client", return_value=mock_redis),
            patch("backend.auth.providers.sso_provider._get_http_client", return_value=mock_http),
        ):
            result = await provider.validate_token("bad-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_logout_success(self, provider):
        """Logout invalidates cache and calls SSO logout endpoint."""
        mock_redis = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response

        with (
            patch("backend.auth.providers.sso_provider._get_redis_client", return_value=mock_redis),
            patch("backend.auth.providers.sso_provider._get_http_client", return_value=mock_http),
        ):
            result = await provider.logout("access-token", "refresh-token")

        assert result is True
        mock_redis.delete.assert_called_once()
        mock_http.post.assert_called_once()

    def test_get_config(self, provider):
        """get_config returns SSO frontend config."""
        config = provider.get_config()
        assert config["provider"] == "sso"
        assert "sso_base_url" in config
        assert "publishable_key" in config
        assert "google_oauth_url" in config


class TestAuthUserModel:
    """Test AuthUser pydantic model."""

    def test_defaults(self):
        user = AuthUser(id="1", email="a@b.com")
        assert user.is_active is True
        assert user.is_verified is False

    def test_serialization_roundtrip(self):
        user = AuthUser(id="1", email="a@b.com", is_active=True, is_verified=True)
        json_str = user.model_dump_json()
        restored = AuthUser.model_validate_json(json_str)
        assert restored == user
