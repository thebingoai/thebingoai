"""LLM Provider factory."""

import logging
from typing import Optional, Callable

from backend.llm.base import BaseLLMProvider
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

# Provider registry
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}

# Plugin-registered provider wrappers (applied in registration order)
_provider_wrappers: list[Callable[[BaseLLMProvider], BaseLLMProvider]] = []


def register_provider_wrapper(fn: Callable[[BaseLLMProvider], BaseLLMProvider]) -> None:
    """Register a wrapper function that transforms a provider instance.

    Wrappers are applied in registration order inside get_provider().
    Plugins should call this during on_startup().
    """
    _provider_wrappers.append(fn)


def get_provider(name: str, model: Optional[str] = None) -> BaseLLMProvider:
    """
    Get an LLM provider instance by name.

    Args:
        name: Provider name (openai, anthropic, ollama)
        model: Optional model override

    Returns:
        Provider instance (with any registered wrappers applied)

    Raises:
        ValueError: If provider not found
    """
    provider_class = _PROVIDERS.get(name.lower())
    if not provider_class:
        available = ", ".join(_PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    provider = provider_class(model=model)
    for wrapper in _provider_wrappers:
        provider = wrapper(provider)
    return provider
