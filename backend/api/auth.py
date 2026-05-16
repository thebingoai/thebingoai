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
    is_subscriber = False
    if "bingo-admin" in get_loaded_plugins():
        try:
            from bingo_admin.models import UserRole
            role_row = db.query(UserRole).filter_by(user_id=current_user.id).first()
            if role_row:
                role = role_row.role
                is_subscriber = bool(role_row.is_subscriber)
            else:
                role = "user"
        except Exception:
            pass  # plugin not fully initialized — return None role

    response = UserResponse.model_validate(current_user)
    response.role = role
    response.is_subscriber = is_subscriber
    if current_user.org_id:
        from backend.config.feature_flags import read_flags
        response.org_feature_flags = read_flags(str(current_user.org_id))
        # Phase 6 of multi-user-org: surface the caller's per-org role so the
        # frontend can gate the Members + Org Credits settings tabs without a
        # second round-trip. Order matters — `admin` outranks `member`/legacy.
        try:
            from bingo_org_governance.models import UserOrgRole
            rows = (
                db.query(UserOrgRole.role)
                .filter(
                    UserOrgRole.user_id == current_user.id,
                    UserOrgRole.org_id == str(current_user.org_id),
                )
                .all()
            )
            held = {r[0] for r in rows}
            if "admin" in held or "data_admin" in held:
                response.org_role = "admin"
            elif "member" in held:
                response.org_role = "member"
            elif held:
                # Edge: only team_admin / unknown legacy roles → expose as-is.
                response.org_role = next(iter(held))
        except ImportError:
            pass  # governance plugin absent
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
