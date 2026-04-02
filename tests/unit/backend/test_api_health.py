"""Tests for health and app-info endpoints."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from backend.api.health import app_info, health_detailed


# ---------------------------------------------------------------------------
# TestAppInfo
# ---------------------------------------------------------------------------

class TestAppInfo:
    """Tests for the app_info() function."""

    @pytest.mark.asyncio
    async def test_returns_version_string(self):
        """app_info returns a dict with a version field."""
        with patch("backend.plugins.loader.get_loaded_plugins", return_value={}):
            result = await app_info()

        assert "version" in result
        assert isinstance(result["version"], str)

    @pytest.mark.asyncio
    async def test_community_edition_when_no_plugins(self):
        """Edition is 'Community' when no plugins are loaded."""
        with patch("backend.plugins.loader.get_loaded_plugins", return_value={}):
            result = await app_info()

        assert result["edition"] == "Community"
        assert result["plugins"] == []

    @pytest.mark.asyncio
    async def test_enterprise_edition_when_plugins_loaded(self):
        """Edition is 'Enterprise' when plugins dict is non-empty."""
        fake_plugin = MagicMock()
        fake_plugin.name = "bingo-sso-auth"
        fake_plugin.version = "1.0.0"
        plugins = {"bingo-sso-auth": fake_plugin}

        with patch("backend.plugins.loader.get_loaded_plugins", return_value=plugins):
            result = await app_info()

        assert result["edition"] == "Enterprise"
        assert len(result["plugins"]) == 1
        assert result["plugins"][0]["name"] == "bingo-sso-auth"
        assert result["plugins"][0]["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# TestHealthDetailed
# ---------------------------------------------------------------------------

class TestHealthDetailed:
    """Tests for the health_detailed() function."""

    @pytest.mark.asyncio
    async def test_all_healthy(self):
        """When Redis and Qdrant are reachable, overall status is 'healthy'."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("backend.api.health.redis.from_url", return_value=mock_redis), \
             patch("backend.api.health.qdrant_health_check", return_value=True):
            result = await health_detailed()

        assert result["status"] == "healthy"
        assert result["checks"]["api"] == "healthy"
        assert result["checks"]["redis"] == "healthy"
        assert result["checks"]["qdrant"] == "healthy"

    @pytest.mark.asyncio
    async def test_degraded_when_redis_fails(self):
        """When Redis is unreachable, overall status is 'degraded'."""
        with patch("backend.api.health.redis.from_url", side_effect=Exception("Connection refused")), \
             patch("backend.api.health.qdrant_health_check", return_value=True):
            result = await health_detailed()

        assert result["status"] == "degraded"
        assert result["checks"]["redis"] == "unhealthy"
        assert result["checks"]["qdrant"] == "healthy"

    @pytest.mark.asyncio
    async def test_degraded_when_qdrant_fails(self):
        """When Qdrant is unreachable, overall status is 'degraded'."""
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        with patch("backend.api.health.redis.from_url", return_value=mock_redis), \
             patch("backend.api.health.qdrant_health_check", return_value=False):
            result = await health_detailed()

        assert result["status"] == "degraded"
        assert result["checks"]["redis"] == "healthy"
        assert result["checks"]["qdrant"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_api_always_healthy(self):
        """The 'api' check is always 'healthy' (it's the running process)."""
        with patch("backend.api.health.redis.from_url", side_effect=Exception("down")), \
             patch("backend.api.health.qdrant_health_check", side_effect=Exception("down")):
            result = await health_detailed()

        assert result["checks"]["api"] == "healthy"
