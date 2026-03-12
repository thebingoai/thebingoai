from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.services import sso_client
from backend.schemas.auth import SSOLogoutRequest, SSOConfigResponse
from backend.schemas.user import UserResponse
from backend.models.user import User
from backend.config import settings

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@router.get("/sso/config", response_model=SSOConfigResponse)
async def get_sso_config():
    """
    Get SSO configuration for the frontend.

    Returns the SSO base URL, publishable key, and OAuth URLs.
    Public endpoint - no authentication required.
    """
    return SSOConfigResponse(
        sso_base_url=settings.sso_base_url,
        publishable_key=settings.sso_publishable_key,
        google_oauth_url=f"{settings.sso_base_url}/api/v1/oauth/google",
    )


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

    # Invalidate the SSO token cache
    await sso_client.invalidate_token_cache(access_token)

    # Tell SSO to blacklist the refresh token
    await sso_client.logout(request.refresh_token)

    return {"message": "Logged out successfully"}
