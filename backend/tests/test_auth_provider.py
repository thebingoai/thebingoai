"""Tests for the auth provider abstraction layer."""

import pytest
from unittest.mock import patch

from backend.auth.base import AuthUser, BaseAuthProvider


class TestAuthProviderFactory:
    """Test factory returns correct provider based on config."""

    def test_get_auth_provider_returns_supabase(self):
        from backend.auth.factory import get_auth_provider
        from backend.auth.providers.supabase_provider import SupabaseAuthProvider

        with patch("backend.auth.factory.settings") as mock_settings:
            mock_settings.auth_provider = "supabase"
            provider = get_auth_provider()
            assert isinstance(provider, SupabaseAuthProvider)
            assert provider.name == "supabase"

    def test_get_auth_provider_unknown_raises(self):
        from backend.auth.factory import get_auth_provider
        with patch("backend.auth.factory.settings") as mock_settings:
            mock_settings.auth_provider = "nonexistent"
            with pytest.raises(ValueError, match="Unknown auth provider 'nonexistent'"):
                get_auth_provider()


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
