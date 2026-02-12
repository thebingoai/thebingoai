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
