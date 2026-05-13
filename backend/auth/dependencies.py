import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from backend.auth.sso import validate_token as sso_validate_token
from backend.database.session import get_db
from backend.models.user import User
from backend.models.team_membership import TeamMembership, MemberRole
from backend.config import settings

logger = logging.getLogger(__name__)

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

    # Validate with SSO
    sso_user = await sso_validate_token(token)
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

    # Bind the user to the request-scoped contextvar so the governance
    # plugin's DataPlane wrap can enforce ACL without threading `user`
    # through every caller. The contextvar resets at request end via FastAPI's
    # task-scoped contextvars; we don't need an explicit reset here.
    from backend.auth.request_context import set_current_request_user
    set_current_request_user(user)

    return user


def _create_user(db: Session, sso_user) -> User:
    """Create a new local User record for a first-time SSO login.

    Three governance modes (checked in priority order):
      - Pending invite for this email → auto-join the inviting org, skip the
        per-user-org-signup path entirely. Used by Phase 2 of multi-user-org
        so invitees never get a stray fresh org.
      - `per_user_org_signup=True` (enterprise lockdown profile): create a
        brand-new Org named after the user's email, put them in a fresh
        per-Org team, mark trial state, and fire `emit_org_created` so
        listeners (e.g. the bingo-admin auto-provisioner) can react.
      - `per_user_org_signup=False` (default / community): join the shared
        DEFAULT_ORG_ID + DEFAULT_TEAM_ID — legacy single-org behaviour.
    """
    try:
        user = User(
            email=sso_user.email,
            sso_id=sso_user.id,
            auth_provider="sso",
            hashed_password=None,
        )
        db.add(user)
        db.flush()  # Get the ID without committing

        org_to_emit = None  # set only when we created a new Org
        invite_consumed = False  # set when we auto-joined via a pending invite

        if settings.enable_governance:
            # Phase 2 (multi-user-org): if there's a pending invite for this
            # email, auto-join the inviter's org instead of creating a new one.
            try:
                from bingo_org_governance.invites import (
                    _consume_invite_for_user,
                    lookup_pending_invite_for_email,
                )
                from bingo_org_governance.audit import write_event
            except ImportError:
                # Governance plugin not installed (community without overlay).
                pending_invite = None
            else:
                pending_invite = lookup_pending_invite_for_email(db, sso_user.email)

            if pending_invite is not None:
                from backend.models.team import Team

                user.org_id = pending_invite.org_id
                first_team = (
                    db.query(Team)
                    .filter(Team.org_id == pending_invite.org_id)
                    .order_by(Team.id)
                    .first()
                )
                if first_team is not None:
                    db.add(TeamMembership(
                        user_id=user.id,
                        team_id=first_team.id,
                        role=MemberRole.MEMBER,
                    ))
                _consume_invite_for_user(db, invite=pending_invite, user=user)
                write_event(
                    db,
                    org_id=pending_invite.org_id,
                    actor_user_id=user.id,
                    event_type="invite.auto_accept",
                    resource_type="org_invite",
                    resource_id=pending_invite.id,
                    details={"email": user.email, "role": pending_invite.role},
                )
                invite_consumed = True
                logger.info(
                    "SSO signup auto-joined org %s via invite %s (email=%s, role=%s)",
                    pending_invite.org_id, pending_invite.id,
                    user.email, pending_invite.role,
                )

        if settings.enable_governance and not invite_consumed:
            if settings.per_user_org_signup:
                # 1 user = 1 Org. Trial state lives on the Organization row.
                import datetime as _dt
                import os as _os
                import uuid as _uuid
                from backend.models.organization import Organization
                from backend.models.team import Team

                trial_days = int(_os.environ.get("TRIAL_PERIOD_DAYS", "14"))
                org = Organization(
                    id=str(_uuid.uuid4()),
                    name=sso_user.email,
                    plan_state="trial",
                    trial_expires_at=_dt.datetime.utcnow() + _dt.timedelta(days=trial_days),
                    feature_flags={"governance_v1": True, "governance_v2": True},
                )
                team = Team(id=str(_uuid.uuid4()), org_id=org.id, name="default")
                db.add(org)
                db.add(team)
                db.flush()  # need org.id + team.id below

                user.org_id = org.id
                db.add(TeamMembership(
                    user_id=user.id,
                    team_id=team.id,
                    role=MemberRole.MEMBER,
                ))
                org_to_emit = org
            else:
                user.org_id = DEFAULT_ORG_ID
                db.add(TeamMembership(
                    user_id=user.id,
                    team_id=DEFAULT_TEAM_ID,
                    role=MemberRole.MEMBER,
                ))

        db.commit()
        db.refresh(user)

        # Fire AFTER commit so listeners (which open their own SessionLocal)
        # see a persisted Org row.
        if org_to_emit is not None:
            from backend.governance.contract import emit_org_created
            emit_org_created(org=org_to_emit, creator_user=user)

        # Seed sample connections for new user
        try:
            from backend.services.seed import seed_sample_connections
            seed_sample_connections(user.id, db)
        except Exception:
            logger.warning("Sample connection seeding failed for user %s", user.id, exc_info=True)

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
