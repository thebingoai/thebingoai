"""
GET /api/llm/models — list available LLM providers and their model options.

Drives the Agent Settings model dropdown. Returns only providers the runtime
considers available (correctly configured API key, reachable Ollama, etc.).
"""
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import settings
from backend.llm.factory import _PROVIDERS

router = APIRouter(prefix="/llm", tags=["llm"])


class ProviderModels(BaseModel):
    name: str
    available: bool
    default_model: Optional[str]
    models: List[str]


class ModelsResponse(BaseModel):
    default_provider: str
    default_model: Optional[str]
    providers: List[ProviderModels]


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    providers: List[ProviderModels] = []

    for name, provider_class in _PROVIDERS.items():
        # Best-effort: instantiating a provider can probe credentials/endpoints.
        # If it fails (e.g. missing key), mark unavailable but still surface
        # the model list so the UI can render a disabled group.
        try:
            instance = provider_class()
            available = instance.is_available()
            default = instance.get_default_model()
        except Exception:
            available = False
            default = None

        providers.append(
            ProviderModels(
                name=name,
                available=available,
                default_model=default,
                models=list(getattr(provider_class, "AVAILABLE_MODELS", []) or []),
            )
        )

    return ModelsResponse(
        default_provider=settings.default_llm_provider,
        default_model=settings.default_llm_model,
        providers=providers,
    )
