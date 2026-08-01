import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
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
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
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

    # NOTE: the account-active check moved into _resolve_local_user
    # (_enforce_account_active) so it can consult both SSO is_active AND the
    # enterprise DB flag once the local user is known. Trial expiry no longer
    # touches SSO is_active — it zeros workspace credits instead.
    if not sso_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified",
        )

    # Sync SQLAlchemy work runs in the threadpool so a slow DB round-trip
    # (NullPool behind PgBouncer = fresh TLS connection per request) never
    # blocks the event loop.
    user = await run_in_threadpool(_resolve_local_user, request, db, sso_user)

    # Bind the user to the request-scoped contextvar so the governance
    # plugin's DataPlane wrap can enforce ACL without threading `user`
    # through every caller. The contextvar resets at request end via FastAPI's
    # task-scoped contextvars; we don't need an explicit reset here.
    from backend.auth.request_context import set_current_request_user
    set_current_request_user(user)

    return user


def _resolve_local_user(request: Request, db: Session, sso_user) -> User:
    """Resolve (or create) the local User for a validated SSO user.

    Runs in the threadpool — keep all sync DB access here, not in
    get_current_user.
    """
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

    _enforce_account_active(db, user, sso_user)
    # Tombstoned (self-serve deleted) accounts are locked out. SSO already
    # deactivates the old sso_id, but this guards against a stale local match
    # resurrecting a renamed account. The fresh-signup path above never reaches
    # here with is_active False (new rows default to True).
    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Multi-workspace: an X-Workspace-Id header selects the active workspace
    # when the user is a member of it. In-memory only; no commit happens here.
    user.active_role = "member"
    active_org = active_role = None
    resolved_workspace = False
    if settings.enable_governance:
        try:
            from bingo_org_governance.deps import resolve_active_workspace
        except ImportError:
            pass
        else:
            header_org = request.headers.get("X-Workspace-Id")
            active_org, active_role = resolve_active_workspace(
                db, user=user, header_org_id=header_org,
            )
            resolved_workspace = True

    # Every DB read this dependency performs is done by here. Ending the
    # transaction now is what stops each authenticated request from pinning a
    # PgBouncer server slot for its whole wall-clock lifetime — including
    # requests that go on to do nothing but LLM, Qdrant or GCS work.
    _end_read_transaction(db)

    # Strictly after _end_read_transaction: user.org_id is a mapped column
    # deliberately overridden in memory and never persisted, so it must not be
    # part of the commit above.
    if resolved_workspace:
        user.home_org_id = str(user.org_id) if user.org_id else None
        if active_org and str(user.org_id) != str(active_org):
            user.org_id = active_org
        user.active_role = active_role
        request.state.active_org_id = active_org
        request.state.active_role = active_role

    return user


def _end_read_transaction(db: Session) -> None:
    """End the dependency's transaction while keeping `user` usable as-is.

    A bare commit() or rollback() ends the transaction but expires every mapped
    attribute in the identity map, so the handler's first `current_user.x` read
    issues a refresh SELECT — which opens a *new* transaction and gives back
    exactly the pooler slot we were trying to release. Suppressing expiry for
    this one commit ends the transaction and leaves the already-loaded row
    readable, with no extra query.

    The session itself is unchanged afterwards: `user` stays attached, so a
    handler that mutates it and commits (api/memory.py does) still persists.
    expire_on_commit is restored so handler commits keep default semantics.
    """
    previous = db.expire_on_commit
    db.expire_on_commit = False
    try:
        db.commit()
    finally:
        db.expire_on_commit = previous


def _enforce_account_active(db: Session, user: User, sso_user) -> None:
    """Account-active gate. Blocks when EITHER source reports inactive.

    - SSO ``is_active``: preserves admin deactivation done in the SSO console
      (Bingo's own deactivate flow flips SSO too, so it is covered here).
    - enterprise ``UserRole.is_active``: the DB flag, when the admin plugin is
      installed.

    Trial expiry no longer sets SSO inactive (it zeros workspace credits), so
    trial users stay SSO-active and are gated only by their org credit pool.

    Upgrade note: a deployment migrating off the old SSO-deactivating trial
    task must run ``scripts/reactivate_trial_victims.py`` once to clear the
    stale SSO ``is_active=False`` left on trial users (signature: SSO inactive
    while ``UserRole.is_active`` is still True) — otherwise the SSO check below
    keeps them locked out.
    """
    if not sso_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    try:
        from bingo_admin.models import UserRole
    except ImportError:
        return

    role_row = db.query(UserRole).filter_by(user_id=user.id).first()
    if role_row is not None and not role_row.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )


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
                logger.info(
                    "SSO signup auto-joined org %s via invite %s (email=%s, role=%s)",
                    pending_invite.org_id, pending_invite.id,
                    user.email, pending_invite.role,
                )

        if settings.enable_governance:
            if settings.per_user_org_signup:
                # 1 user = 1 Org. Trial state lives on the Organization row.
                import datetime as _dt
                import os as _os
                import uuid as _uuid
                from backend.models.organization import Organization
                from backend.models.team import Team

                trial_days = int(_os.environ.get("TRIAL_PERIOD_DAYS", "14"))
                # organizations.name is UNIQUE. A tombstoned prior account can leave
                # a stale org still named after this email (deletion frees the email
                # but not the org name); reusing it would collide. Suffix the name
                # when it's already taken so re-signup succeeds.
                org_name = sso_user.email
                if db.query(Organization.id).filter(Organization.name == org_name).first() is not None:
                    org_name = f"{sso_user.email}-{_uuid.uuid4().hex[:8]}"
                org = Organization(
                    id=str(_uuid.uuid4()),
                    name=org_name,
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
                from bingo_org_governance.roles import assign_role
                assign_role(db, user_id=user.id, org_id=org.id, role="admin")
                org_to_emit = org
            else:
                user.org_id = DEFAULT_ORG_ID
                db.add(TeamMembership(
                    user_id=user.id,
                    team_id=DEFAULT_TEAM_ID,
                    role=MemberRole.MEMBER,
                ))
                from bingo_org_governance.roles import assign_role
                assign_role(db, user_id=user.id, org_id=DEFAULT_ORG_ID, role="member")

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


def forbid_viewer(current_user: User = Depends(get_current_user)) -> User:
    """403 when the active workspace role is 'viewer' (read-only guest).
    In community/no-governance deploys active_role is always 'member', so this
    is a no-op there."""
    if getattr(current_user, "active_role", None) == "viewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewers cannot perform this action in this workspace.",
        )
    return current_user
