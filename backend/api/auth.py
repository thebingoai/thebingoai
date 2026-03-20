from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.factory import get_auth_provider
from backend.schemas.auth import SSOLogoutRequest
from backend.schemas.user import UserResponse
from backend.models.user import User
from backend.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@router.get("/config")
async def get_auth_config():
    """
    Get auth provider configuration for the frontend.

    Returns provider-specific config (URLs, public keys, etc.).
    Public endpoint - no authentication required.
    """
    provider = get_auth_provider()
    return provider.get_config()


# Keep old endpoint as alias for backwards compatibility during frontend rollout
@router.get("/sso/config")
async def get_sso_config():
    """Deprecated: use /auth/config instead."""
    provider = get_auth_provider()
    return provider.get_config()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Requires: Bearer token in Authorization header
    """
    return current_user


@router.post("/logout")
async def logout(
    request: SSOLogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
):
    """
    Logout: blacklist the refresh token on SSO and invalidate local cache.

    Requires: Bearer token in Authorization header
    Body: { "refresh_token": "..." }
    """
    access_token = credentials.credentials

    # Logout via auth provider (invalidate cache + blacklist refresh token)
    provider = get_auth_provider()
    await provider.logout(access_token, request.refresh_token)

    return {"message": "Logged out successfully"}
