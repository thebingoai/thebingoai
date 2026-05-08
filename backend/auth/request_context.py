"""Request-scoped current-user contextvar — companion to system_context.

Phase G v2.c needs to enforce ACL inside DataPlane.query, but the DataPlane
signature doesn't carry a user. Rather than threading `user` through every
caller, FastAPI's `get_current_user` dependency populates a contextvar at
the start of each request; the plugin's DataPlane wrap reads it.

When neither `current_request_user()` nor `current_system_context()` is set
(e.g. a Celery task that hasn't entered a system_context block, or an
internal call from a script), the wrap writes an audit row and passes
through without ACL enforcement — over-strictness here would break
unaudited internal flows. The expected pattern is: every long-running
background task wraps its work in `with system_context(...)`.
"""
from __future__ import annotations

import contextvars
from typing import Any, Optional

_current_request_user: contextvars.ContextVar[Optional[Any]] = contextvars.ContextVar(
    "bingo_current_request_user",
    default=None,
)


def current_request_user() -> Optional[Any]:
    """Return the User bound to the current request, or None."""
    return _current_request_user.get()


def set_current_request_user(user: Optional[Any]) -> contextvars.Token:
    """Set the current-request user. Returns a Token for resetting.

    Called by `get_current_user` at the start of each FastAPI request.
    """
    return _current_request_user.set(user)


def reset_current_request_user(token: contextvars.Token) -> None:
    """Restore the previous binding using the Token from set_current_request_user."""
    _current_request_user.reset(token)
