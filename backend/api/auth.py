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
async def get_auth_config(request: Request):
    """
    Get auth provider configuration for the frontend.

    Returns provider-specific config (URLs, public keys, etc.) plus the runtime
    maintenance-mode state. Public endpoint - no authentication required. The
    `maintenance.bypass_active` flag reflects whether the caller already holds a
    valid HttpOnly bypass cookie, so the frontend can decide whether to render
    the maintenance page or the login form without exposing the bypass key.
    """
    config = sso_get_config()
    config["maintenance"] = {
        "active": settings.maintenance_mode,
        "bypass_active": request.cookies.get("maint_bypass") == "1",
        "message": settings.maintenance_message,
    }
    return config


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
            db.rollback()  # aborted transaction blocks subsequent queries on same session

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
):
    """
    Logout: invalidate tokens via the configured auth provider.

    Best-effort — does NOT require a valid/unexpired token. The access token is
    forwarded to SSO for invalidation as-is; an already-expired token is fine
    (it's being discarded anyway). Gating this on get_current_user caused a 401
    whenever the access token had expired by logout time.

    Requires: Bearer token in Authorization header
    Body: { "refresh_token": "..." }
    """
    access_token = credentials.credentials

    await sso_logout(access_token, request.refresh_token)

    return {"message": "Logged out successfully"}
