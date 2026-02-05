"""LLM Provider factory."""

from typing import Optional

from backend.llm.base import BaseLLMProvider
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.config import settings


# Provider registry
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str, model: Optional[str] = None) -> BaseLLMProvider:
    """
    Get an LLM provider instance by name.

    Args:
        name: Provider name (openai, anthropic, ollama)
        model: Optional model override

    Returns:
        Provider instance

    Raises:
        ValueError: If provider not found
    """
    provider_class = _PROVIDERS.get(name.lower())
    if not provider_class:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    return provider_class(model=model)


def get_default_provider() -> BaseLLMProvider:
    """Get the default provider from settings."""
    return get_provider(
        settings.default_llm_provider,
        settings.default_llm_model
    )


def list_available_providers() -> list[dict]:
    """List all providers and their availability."""
    result = []
    for name, provider_class in _PROVIDERS.items():
        provider = provider_class()
        result.append({
            "name": name,
            "available": provider.is_available(),
            "default_model": provider.get_default_model()
        })
    return result


def register_provider(name: str, provider_class: type[BaseLLMProvider]) -> None:
    """Register a custom provider."""
    _PROVIDERS[name.lower()] = provider_class
