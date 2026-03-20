"""Tests for auth provider factory and Supabase provider."""

import time
from unittest.mock import patch

import jwt as pyjwt
import pytest


# ---------------------------------------------------------------------------
# Auth factory tests
# ---------------------------------------------------------------------------

class TestAuthFactory:
    def test_register_and_get_provider(self):
        from backend.auth.factory import _providers, register_provider, get_auth_provider
        from backend.auth.base import BaseAuthProvider

        class FakeProvider(BaseAuthProvider):
            @property
            def name(self):
                return "fake"
            async def validate_token(self, access_token):
                return None
            async def logout(self, access_token, refresh_token):
                return True
            def get_config(self):
                return {}

        register_provider("fake", FakeProvider)
        assert "fake" in _providers

        with patch("backend.auth.factory.settings") as mock_settings:
            mock_settings.auth_provider = "fake"
            provider = get_auth_provider()
            assert provider.name == "fake"

        # Cleanup
        del _providers["fake"]

    def test_unknown_provider_raises(self):
        from backend.auth.factory import get_auth_provider

        with patch("backend.auth.factory.settings") as mock_settings:
            mock_settings.auth_provider = "nonexistent"
            with pytest.raises(ValueError, match="Unknown auth provider 'nonexistent'"):
                get_auth_provider()

    def test_supabase_auto_registered(self):
        from backend.auth.factory import _providers
        assert "supabase" in _providers


# ---------------------------------------------------------------------------
# Plugin auth_providers registration test
# ---------------------------------------------------------------------------

class TestPluginAuthProviders:
    def test_plugin_base_has_auth_providers_method(self):
        from backend.plugins.base import BingoPlugin
        # Verify the method exists and returns empty by default
        class MinimalPlugin(BingoPlugin):
            @property
            def name(self): return "minimal"
            @property
            def version(self): return "0.0.1"
        plugin = MinimalPlugin()
        assert plugin.auth_providers() == []


# ---------------------------------------------------------------------------
# Supabase provider tests
# ---------------------------------------------------------------------------

JWT_SECRET = "test-jwt-secret-for-unit-tests-must-be-long-enough"


def _make_jwt(payload: dict, secret: str = JWT_SECRET) -> str:
    return pyjwt.encode(payload, secret, algorithm="HS256")


class TestSupabaseProvider:
    @pytest.fixture
    def provider(self):
        from backend.auth.providers.supabase_provider import SupabaseAuthProvider
        return SupabaseAuthProvider()

    @pytest.fixture(autouse=True)
    def mock_settings(self):
        with patch("backend.auth.providers.supabase_provider.settings") as mock:
            mock.supabase_jwt_secret = JWT_SECRET
            mock.supabase_url = "https://test.supabase.co"
            mock.supabase_anon_key = "test-anon-key"
            yield mock

    def test_name(self, provider):
        assert provider.name == "supabase"

    @pytest.mark.asyncio
    async def test_validate_valid_token(self, provider):
        token = _make_jwt({
            "sub": "user-123",
            "email": "test@example.com",
            "email_confirmed_at": "2024-01-01T00:00:00Z",
            "aud": "authenticated",
        })
        user = await provider.validate_token(token)
        assert user is not None
        assert user.id == "user-123"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_verified is True

    @pytest.mark.asyncio
    async def test_validate_unverified_email(self, provider):
        token = _make_jwt({
            "sub": "user-456",
            "email": "unverified@example.com",
            "email_confirmed_at": None,
            "aud": "authenticated",
        })
        user = await provider.validate_token(token)
        assert user is not None
        assert user.is_verified is False

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self, provider):
        user = await provider.validate_token("invalid.jwt.token")
        assert user is None

    @pytest.mark.asyncio
    async def test_validate_wrong_secret(self, provider):
        token = _make_jwt(
            {"sub": "user-789", "email": "test@example.com", "aud": "authenticated"},
            secret="wrong-secret-that-does-not-match",
        )
        user = await provider.validate_token(token)
        assert user is None

    @pytest.mark.asyncio
    async def test_validate_expired_token(self, provider):
        token = _make_jwt({
            "sub": "user-exp",
            "email": "expired@example.com",
            "aud": "authenticated",
            "exp": int(time.time()) - 3600,
        })
        user = await provider.validate_token(token)
        assert user is None

    @pytest.mark.asyncio
    async def test_validate_wrong_audience(self, provider):
        token = _make_jwt({
            "sub": "user-aud",
            "email": "wrong-aud@example.com",
            "aud": "service_role",
        })
        user = await provider.validate_token(token)
        assert user is None

    @pytest.mark.asyncio
    async def test_logout_noop(self, provider):
        result = await provider.logout("token", "refresh")
        assert result is True

    def test_get_config(self, provider):
        config = provider.get_config()
        assert config["provider"] == "supabase"
        assert config["supabase_url"] == "https://test.supabase.co"
        assert config["supabase_anon_key"] == "test-anon-key"
