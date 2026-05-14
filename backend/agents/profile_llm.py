"""Resolve LLM call settings (model, temperature, max_tokens) from an
AgentProfile's *published* snapshot. Draft edits are ignored — same gating
applied to prompt sections and avatar — so the user has to Publish before
chat behavior changes.
"""

from typing import Optional, Tuple

from backend.llm.base import BaseLLMProvider
from backend.llm.factory import _PROVIDERS, get_provider
from backend.config import settings


def _provider_for_model(model: str) -> Optional[str]:
    """Return the provider name whose AVAILABLE_MODELS contains `model`, or None."""
    for name, cls in _PROVIDERS.items():
        if model in (getattr(cls, "AVAILABLE_MODELS", []) or []):
            return name
    return None


def resolve_published_llm(
    profile: object,
) -> Tuple[BaseLLMProvider, Optional[float], Optional[int]]:
    """Build the provider + return (provider, temperature, max_tokens) using the
    profile's published_snapshot. Falls back to global defaults when the user
    hasn't published or hasn't customized that field."""
    snap = getattr(profile, "published_snapshot", None) or {}
    model = (snap.get("default_model") or "").strip() or None
    temperature = snap.get("temperature")
    max_tokens = snap.get("max_output_tokens")

    provider_name = _provider_for_model(model) if model else None
    provider_name = provider_name or settings.default_llm_provider
    provider = get_provider(provider_name, model=model)
    return provider, temperature, max_tokens
