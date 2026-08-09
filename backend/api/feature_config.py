from fastapi import APIRouter
from backend.config import settings

router = APIRouter(prefix="/config", tags=["config"])


def _is_real_key(value: str | None) -> bool:
    # `.env.example` ships placeholders like "sk-..." / "sk-ant-..."; reject any value
    # containing literal "..." since real API keys never use it as a delimiter.
    if not value:
        return False
    stripped = value.strip()
    return bool(stripped) and "..." not in stripped


@router.get("")
async def get_config():
    from backend.plugins.loader import get_loaded_plugins
    loaded = get_loaded_plugins()
    credits_enabled = "bingo-admin" in loaded  # bingo-admin replaces bingo-credits
    admin_enabled = "bingo-admin" in loaded
    telegram_enabled = "bingo-telegram" in loaded
    return {
        "governance_enabled": settings.enable_governance,
        "chat_export_enabled": settings.chat_export_enabled,
        "credits_enabled": credits_enabled,
        "admin_enabled": admin_enabled,
        "telegram_enabled": telegram_enabled,
        "providers": {
            "openai": {
                "configured": _is_real_key(settings.openai_api_key),
                "base_url": "https://api.openai.com/v1",
            },
            "anthropic": {
                "configured": _is_real_key(settings.anthropic_api_key),
                "base_url": "https://api.anthropic.com",
            },
        },
    }
