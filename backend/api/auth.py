from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.auth.sso import get_config as sso_get_config, logout as sso_logout
from backend.schemas.auth import LogoutRequest
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
    return sso_get_config()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current authenticated user. Includes role if bingo-admin plugin is loaded."""
    from backend.plugins.loader import get_loaded_plugins
    role = None
    if "bingo-admin" in get_loaded_plugins():
        try:
            from bingo_admin.models import UserRole
            role_row = db.query(UserRole).filter_by(user_id=current_user.id).first()
            role = role_row.role if role_row else "user"
        except Exception:
            pass  # plugin not fully initialized — return None role

    response = UserResponse.model_validate(current_user)
    response.role = role
    return response


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
):
    """
    Logout: invalidate tokens via the configured auth provider.

    Requires: Bearer token in Authorization header
    Body: { "refresh_token": "..." }
    """
    access_token = credentials.credentials

    await sso_logout(access_token, request.refresh_token)

    return {"message": "Logged out successfully"}
