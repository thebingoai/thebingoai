from fastapi import APIRouter
from backend.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("")
async def get_config():
    return {
        "governance_enabled": settings.enable_governance,
    }
