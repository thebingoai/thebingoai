"""Tests for the LLM provider factory and registry."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# get_provider
# ---------------------------------------------------------------------------

class TestGetProvider:
    """Tests for get_provider factory function."""

    @patch("backend.llm.factory.OpenAIProvider")
    def test_openai_provider(self, MockOpenAI):
        """get_provider('openai') instantiates and returns an OpenAIProvider."""
        from backend.llm.factory import get_provider, _PROVIDERS
        sentinel = MagicMock()
        MockOpenAI.return_value = sentinel

        # Temporarily replace registry entry with our mock
        original = _PROVIDERS["openai"]
        _PROVIDERS["openai"] = MockOpenAI
        try:
            result = get_provider("openai")
            MockOpenAI.assert_called_once_with(model=None)
            assert result is sentinel
        finally:
            _PROVIDERS["openai"] = original

    @patch("backend.llm.factory.AnthropicProvider")
    def test_anthropic_provider(self, MockAnthropic):
        """get_provider('anthropic') instantiates and returns an AnthropicProvider."""
        from backend.llm.factory import get_provider, _PROVIDERS
        sentinel = MagicMock()
        MockAnthropic.return_value = sentinel

        original = _PROVIDERS["anthropic"]
        _PROVIDERS["anthropic"] = MockAnthropic
        try:
            result = get_provider("anthropic")
            MockAnthropic.assert_called_once_with(model=None)
            assert result is sentinel
        finally:
            _PROVIDERS["anthropic"] = original

    @patch("backend.llm.factory.OllamaProvider")
    def test_ollama_provider(self, MockOllama):
        """get_provider('ollama') instantiates and returns an OllamaProvider."""
        from backend.llm.factory import get_provider, _PROVIDERS
        sentinel = MagicMock()
        MockOllama.return_value = sentinel

        original = _PROVIDERS["ollama"]
        _PROVIDERS["ollama"] = MockOllama
        try:
            result = get_provider("ollama")
            MockOllama.assert_called_once_with(model=None)
            assert result is sentinel
        finally:
            _PROVIDERS["ollama"] = original

    def test_unknown_provider_raises_value_error(self):
        """Requesting an unregistered provider name raises ValueError."""
        from backend.llm.factory import get_provider

        with pytest.raises(ValueError, match="Unknown provider 'nonexistent'"):
            get_provider("nonexistent")

    def test_model_parameter_passed_through(self):
        """The model kwarg is forwarded to the provider constructor."""
        from backend.llm.factory import get_provider, _PROVIDERS

        mock_cls = MagicMock()
        _PROVIDERS["_test_"] = mock_cls
        try:
            get_provider("_test_", model="custom-model-v2")
            mock_cls.assert_called_once_with(model="custom-model-v2")
        finally:
            del _PROVIDERS["_test_"]

    def test_case_insensitive_lookup(self):
        """Provider names are looked up case-insensitively."""
        from backend.llm.factory import get_provider, _PROVIDERS

        mock_cls = MagicMock()
        _PROVIDERS["openai"] = mock_cls
        try:
            get_provider("OpenAI")
            mock_cls.assert_called_once_with(model=None)
        finally:
            # Restore real class
            from backend.llm.openai_provider import OpenAIProvider
            _PROVIDERS["openai"] = OpenAIProvider
