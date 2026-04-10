from fastapi import APIRouter
from backend.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    from backend.plugins.loader import get_loaded_plugins
    credits_enabled = "bingo-credits" in get_loaded_plugins()
    return {
        "governance_enabled": settings.enable_governance,
        "credits_enabled": credits_enabled,
    }
