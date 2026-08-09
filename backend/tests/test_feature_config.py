"""Tests for the /api/config feature flags endpoint."""

from unittest.mock import patch

import pytest


class TestGetConfig:
    """Test the get_config endpoint returns correct feature flags."""

    @pytest.mark.asyncio
    async def test_telegram_enabled_when_plugin_loaded(self):
        from backend.api.feature_config import get_config

        with patch('backend.api.feature_config.get_loaded_plugins', return_value={'bingo-telegram', 'bingo-admin'}):
            result = await get_config()

        assert result['telegram_enabled'] is True

    @pytest.mark.asyncio
    async def test_telegram_disabled_when_plugin_not_loaded(self):
        from backend.api.feature_config import get_config

        with patch('backend.api.feature_config.get_loaded_plugins', return_value=set()):
            result = await get_config()

        assert result['telegram_enabled'] is False

    @pytest.mark.asyncio
    async def test_telegram_disabled_with_other_plugins_loaded(self):
        from backend.api.feature_config import get_config

        with patch('backend.api.feature_config.get_loaded_plugins', return_value={'bingo-admin', 'bingo-csv-connector'}):
            result = await get_config()

        assert result['telegram_enabled'] is False

    @pytest.mark.asyncio
    async def test_admin_enabled_when_bingo_admin_loaded(self):
        from backend.api.feature_config import get_config

        with patch('backend.api.feature_config.get_loaded_plugins', return_value={'bingo-admin'}):
            result = await get_config()

        assert result['admin_enabled'] is True
        assert result['credits_enabled'] is True

    @pytest.mark.asyncio
    async def test_admin_disabled_without_bingo_admin(self):
        from backend.api.feature_config import get_config

        with patch('backend.api.feature_config.get_loaded_plugins', return_value=set()):
            result = await get_config()

        assert result['admin_enabled'] is False
        assert result['credits_enabled'] is False

    @pytest.mark.asyncio
    async def test_response_contains_all_expected_keys(self):
        from backend.api.feature_config import get_config

        with patch('backend.api.feature_config.get_loaded_plugins', return_value=set()):
            result = await get_config()

        assert 'governance_enabled' in result
        assert 'chat_export_enabled' in result
        assert 'credits_enabled' in result
        assert 'admin_enabled' in result
        assert 'telegram_enabled' in result

    def test_chat_export_defaults_off(self):
        from backend.config import Settings

        # The env the app ships with, not the ambient dev .env.
        assert Settings.model_fields['chat_export_enabled'].default is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize('flag', [True, False])
    async def test_chat_export_mirrors_the_setting(self, flag):
        from backend.api.feature_config import get_config
        from backend.config import settings

        # get_config imports get_loaded_plugins lazily inside the function body, so it
        # resolves off the loader module — patching the api module misses it.
        with patch('backend.plugins.loader.get_loaded_plugins', return_value=set()), \
             patch.object(settings, 'chat_export_enabled', flag):
            result = await get_config()

        assert result['chat_export_enabled'] is flag
