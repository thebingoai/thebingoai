"""System-context primitive for background tasks (Phase 0 — preflight).

Lets background workers (Pipeline runner, dbt subprocess, profiling, governance
audit) run code that the enterprise governance plugin (Phase G) would otherwise
gate on per-user RBAC. The context manager pushes a frame onto a contextvars
stack; the governance plugin reads `current_system_context()` and, when set,
skips the user-permission check and writes an `audit_events` row with
`actor_user_id = NULL` and `actor = "__system__"`.

Phase 0 ships only the marker + stack reader; the audit write lives in Phase G.

The `scope` field is typed `Any | None` because `OwnerScope` lands in Phase 1.
Tighten the annotation when Phase 1 introduces the value object.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterator

SYSTEM_ACTOR = "__system__"


@dataclass(frozen=True)
class SystemContext:
    actor: str = SYSTEM_ACTOR
    scope: Any | None = None
    reason: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


_stack: contextvars.ContextVar[tuple[SystemContext, ...]] = contextvars.ContextVar(
    "bingo_system_context_stack",
    default=(),
)


def current_system_context() -> SystemContext | None:
    """Return the innermost active SystemContext, or None outside any context."""
    stack = _stack.get()
    return stack[-1] if stack else None


@contextmanager
def system_context(reason: str, scope: Any | None = None) -> Iterator[SystemContext]:
    """Push a SystemContext for the duration of the with-block.

    Args:
        reason: Required short description, recorded by Phase G's audit hook.
        scope: Optional OwnerScope (Phase 1+). May be None for cross-scope
            system tasks like cleanup or migration.

    Raises:
        ValueError: If `reason` is empty.
    """
    if not reason:
        raise ValueError("system_context requires a non-empty reason")

    ctx = SystemContext(scope=scope, reason=reason)
    token = _stack.set(_stack.get() + (ctx,))
    try:
        yield ctx
    finally:
        _stack.reset(token)
