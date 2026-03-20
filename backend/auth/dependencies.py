from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.auth.factory import get_auth_provider
from backend.database.session import get_db
from backend.models.user import User
from backend.models.team_membership import TeamMembership, MemberRole
from backend.config import settings

DEFAULT_ORG_ID = 'org-default-00000000-0000-0000-0000'
DEFAULT_TEAM_ID = 'team-default-00000000-0000-0000-0000'

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get the current authenticated user via SSO token validation.

    Flow:
    1. Extract Bearer token
    2. Call SSO validate_token() -> SSOUser
    3. If None -> 401
    4. If not active or not verified -> 403
    5. Lookup local User by sso_id
    6. If not found, lookup by email (handles pre-SSO migration users)
    7. If not found at all -> auto-create User with sso_id
    8. If found by email but no sso_id -> link: set sso_id and auth_provider
    9. Return User
    """
    token = credentials.credentials

    # Validate with auth provider
    auth_provider = get_auth_provider()
    sso_user = await auth_provider.validate_token(token)
    if sso_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not sso_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if not sso_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified",
        )

    # Look up by sso_id first
    user = db.query(User).filter(User.sso_id == sso_user.id).first()

    if user is None:
        # Look up by email (handles pre-SSO users whose records exist without sso_id)
        user = db.query(User).filter(User.email == sso_user.email).first()

        if user is not None:
            # Link existing user to SSO
            user.sso_id = sso_user.id
            user.auth_provider = "sso"
            db.commit()
            db.refresh(user)
        else:
            # Auto-create new user
            user = _create_user(db, sso_user)

    return user


def _create_user(db: Session, sso_user) -> User:
    """Create a new local User record for a first-time SSO login."""
    try:
        user = User(
            email=sso_user.email,
            sso_id=sso_user.id,
            auth_provider="sso",
            hashed_password=None,
        )
        db.add(user)
        db.flush()  # Get the ID without committing

        if settings.enable_governance:
            user.org_id = DEFAULT_ORG_ID
            membership = TeamMembership(
                user_id=user.id,
                team_id=DEFAULT_TEAM_ID,
                role=MemberRole.MEMBER,
            )
            db.add(membership)

        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        # Race condition: another request created the user simultaneously
        db.rollback()
        user = db.query(User).filter(User.sso_id == sso_user.id).first()
        if user is None:
            user = db.query(User).filter(User.email == sso_user.email).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not create user account. Please try again.",
            )
        return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """FastAPI dependency to ensure user is active (kept for backwards compatibility)."""
    return current_user
