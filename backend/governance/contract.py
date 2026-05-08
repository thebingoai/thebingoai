"""Governance contract — community-side seam for the enterprise governance plugin.

Phase G of `data-platform-v1`. Community ships only the contract; the actual
ACL / policy / audit logic lives in `plugins/bingo-org-governance/` (enterprise).
When the plugin is absent, `check` is a no-op (Permit) and no listeners fire,
so community-edition behavior is unchanged.

The plugin overrides `check` via `register_check` and subscribes to lifecycle
events (`register_org_created_listener` / `register_resource_created_listener`)
during its `on_startup`.

Honors the system-context bypass from Phase 0 directly: when a background task
runs inside `with system_context(...)`, `check` short-circuits to Permit before
ever reaching the registered impl, so plugin code doesn't have to repeat the
pattern.

## Pragmatic note on the v1 "decorator"

The Phase G plan calls for `@requires(action, resource_loader)` on FastAPI
endpoints. The shipped form is the explicit `require(...)` guard called inline
at the top of each route handler. Reasons:

- FastAPI's `Depends` injection happens BEFORE the wrapped function runs, so a
  decorator can't reliably resolve `current_user` from kwargs across endpoints
  with varying parameter names.
- The resource frequently needs the DB session + path params to resolve, which
  is awkward to express in a static decorator.
- The inline form is identical at the call site (one line) and easier to read.

The "via lazy-import / no-op contract" requirement still holds: `require` is
the function called from community endpoints; the registered `check` impl
lives in the plugin and falls back to Permit when the plugin is absent.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Protocol

from backend.auth.system_context import current_system_context

logger = logging.getLogger(__name__)


class CheckFn(Protocol):
    def __call__(self, *, user: Any, action: str, resource: Any) -> bool: ...


def _default_check(*, user: Any, action: str, resource: Any) -> bool:
    return True


_check_fn: CheckFn = _default_check


def check(*, user: Any, action: str, resource: Any) -> bool:
    """Return True if the user is permitted to perform the action on the resource.

    Default is no-op Permit. The governance plugin overrides via
    `register_check` during its `on_startup`. System-context tasks always
    Permit without consulting the registered impl.
    """
    if current_system_context() is not None:
        return True
    return _check_fn(user=user, action=action, resource=resource)


def require(*, user: Any, action: str, resource: Any) -> None:
    """Inline guard. Raises HTTPException 403 if check returns False.

    Call at the top of any FastAPI route that needs governance gating:

        @router.post("/connections")
        async def create(...):
            require(user=current_user, action="create", resource={"type": "connection"})
            ...
    """
    if check(user=user, action=action, resource=resource):
        return
    # Lazy import: keep contract module import-time-cheap and free of
    # FastAPI dependencies until the deny path actually fires.
    from fastapi import HTTPException, status as http_status

    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail=f"Governance policy denies {action!r} on this resource",
    )


def register_check(fn: CheckFn) -> None:
    """Override the check function — called by the governance plugin on_startup."""
    global _check_fn
    _check_fn = fn
    logger.info(
        "governance.contract: check fn registered (%s)",
        getattr(fn, "__qualname__", repr(fn)),
    )


def reset_check() -> None:
    """Restore the no-op default. Used by tests; never by production code."""
    global _check_fn
    _check_fn = _default_check


# Lifecycle events ------------------------------------------------------------

_org_created_listeners: list[Callable[..., None]] = []
_resource_created_listeners: list[Callable[..., None]] = []


def register_org_created_listener(fn: Callable[..., None]) -> None:
    """Subscribe to org.created events. Idempotent: same fn won't be added twice."""
    if fn not in _org_created_listeners:
        _org_created_listeners.append(fn)


def emit_org_created(*, org: Any, creator_user: Any) -> None:
    """Fire after a new Organization row is committed in api/organizations.py.

    Listener errors are logged and swallowed — org creation must not fail just
    because the governance plugin has a bug.
    """
    for fn in _org_created_listeners:
        try:
            fn(org=org, creator_user=creator_user)
        except Exception:
            logger.exception(
                "governance.contract: org_created listener %r raised; ignoring",
                getattr(fn, "__qualname__", repr(fn)),
            )


def register_resource_created_listener(fn: Callable[..., None]) -> None:
    """Subscribe to resource.created events. Idempotent.

    Listener signature: `fn(*, resource_type: str, resource: Any, creator_user: Any)`.
    Used by the governance plugin to seed default ACL grants when a new
    org-scoped resource lands.
    """
    if fn not in _resource_created_listeners:
        _resource_created_listeners.append(fn)


def emit_resource_created(*, resource_type: str, resource: Any, creator_user: Any) -> None:
    """Fire after any governable resource (connection, pipeline, dbt_model, …)
    is committed. Listener errors are logged and swallowed.
    """
    for fn in _resource_created_listeners:
        try:
            fn(resource_type=resource_type, resource=resource, creator_user=creator_user)
        except Exception:
            logger.exception(
                "governance.contract: resource_created listener %r raised; ignoring",
                getattr(fn, "__qualname__", repr(fn)),
            )


def reset_listeners() -> None:
    """Drop all registered listeners. Used by tests; never by production code."""
    _org_created_listeners.clear()
    _resource_created_listeners.clear()
    _user_offboarded_listeners.clear()


# ---------------------------------------------------------------------------
# v1.c.1 — Connector dedup nudge
# ---------------------------------------------------------------------------

class DedupCheckFn(Protocol):
    def __call__(self, *, user: Any, connection_payload: dict) -> Optional[str]: ...


def _default_dedup_check(*, user: Any, connection_payload: dict) -> Optional[str]:
    return None


_dedup_check_fn: DedupCheckFn = _default_dedup_check


def find_duplicate_connection(*, user: Any, connection_payload: dict) -> Optional[str]:
    """Look for an existing connection in caller's org with the same fingerprint.

    Returns the matching connection id (string) or None. Default is no-op
    (None); the bingo-org-governance plugin registers an impl that uses the
    connector's fingerprint(connection) helper to compute and SELECT.
    """
    return _dedup_check_fn(user=user, connection_payload=connection_payload)


def register_dedup_check(fn: DedupCheckFn) -> None:
    """Override the dedup-check function — called by the governance plugin on_startup."""
    global _dedup_check_fn
    _dedup_check_fn = fn
    logger.info(
        "governance.contract: dedup_check fn registered (%s)",
        getattr(fn, "__qualname__", repr(fn)),
    )


def reset_dedup_check() -> None:
    """Restore the no-op default. Used by tests; never by production code."""
    global _dedup_check_fn
    _dedup_check_fn = _default_dedup_check


# ---------------------------------------------------------------------------
# v1.c.3 — User offboarding lifecycle
# ---------------------------------------------------------------------------

_user_offboarded_listeners: list[Callable[..., None]] = []


def register_user_offboarded_listener(fn: Callable[..., None]) -> None:
    """Subscribe to user.offboarded events. Idempotent.

    Listener signature: `fn(*, user_id: str, org_id: str)`. Used by the
    governance plugin to transfer user-scoped resources to the org and
    revoke role assignments.
    """
    if fn not in _user_offboarded_listeners:
        _user_offboarded_listeners.append(fn)


def emit_user_offboarded(*, user_id: str, org_id: str) -> None:
    """Fire when a user is removed from an Organization (deactivated, kicked,
    etc.). Listener errors are logged and swallowed.
    """
    for fn in _user_offboarded_listeners:
        try:
            fn(user_id=user_id, org_id=org_id)
        except Exception:
            logger.exception(
                "governance.contract: user_offboarded listener %r raised; ignoring",
                getattr(fn, "__qualname__", repr(fn)),
            )
