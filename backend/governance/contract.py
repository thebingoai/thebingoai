"""Governance contract — community-side seam for the enterprise governance plugin.

Phase G of `data-platform-v1`. Community ships only the contract; the actual
ACL / policy / audit logic lives in `plugins/bingo-org-governance/` (enterprise).
When the plugin is absent, `check` is a no-op (Permit) and no listeners fire,
so community-edition behavior is unchanged.

The plugin overrides `check` via `register_check` and subscribes to lifecycle
events (`register_org_created_listener`, etc.) during its `on_startup`.

Honors the system-context bypass from Phase 0 directly: when a background task
runs inside `with system_context(...)`, `check` short-circuits to Permit before
ever reaching the registered impl, so plugin code doesn't have to repeat the
pattern.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Protocol

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


def register_org_created_listener(fn: Callable[..., None]) -> None:
    """Subscribe to org.created events. Idempotent: same fn won't be added twice."""
    if fn not in _org_created_listeners:
        _org_created_listeners.append(fn)


def emit_org_created(*, org: Any, creator_user: Any) -> None:
    """Fire after a new Organization row is committed in api/organizations.py.

    Listener errors are logged and swallowed — org creation must not fail just
    because the governance plugin has a bug. The listener can re-raise its own
    transactional errors, which the caller is free to handle, but exceptions
    here always degrade to "no governance hook ran for this org."
    """
    for fn in _org_created_listeners:
        try:
            fn(org=org, creator_user=creator_user)
        except Exception:
            logger.exception(
                "governance.contract: org_created listener %r raised; ignoring",
                getattr(fn, "__qualname__", repr(fn)),
            )


def reset_listeners() -> None:
    """Drop all registered listeners. Used by tests; never by production code."""
    _org_created_listeners.clear()
