from fastapi import APIRouter
from backend.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    from backend.plugins.loader import get_loaded_plugins
    loaded = get_loaded_plugins()
    credits_enabled = "bingo-admin" in loaded  # bingo-admin replaces bingo-credits
    admin_enabled = "bingo-admin" in loaded
    telegram_enabled = "bingo-telegram" in loaded
    return {
        "governance_enabled": settings.enable_governance,
        "credits_enabled": credits_enabled,
        "admin_enabled": admin_enabled,
        "telegram_enabled": telegram_enabled,
    }
