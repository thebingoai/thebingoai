"""Hot-path REST handlers must not run blocking work on the event loop.

Prod runs UVICORN_WORKERS=1, so an `async def` handler doing sync SQLAlchemy
freezes the pod's only loop while QueuePool checkout does a blocking
`threading.wait` (up to pool_timeout). Under load that stalls /health, readiness
pulls the pod, and the survivors inherit the traffic — the 2026-08-31 outage
shape, pinned by loop_watchdog stack dumps at api/auth.py get_current_user_info.

Declared as plain `def`, Starlette runs these handlers in its threadpool: pool
exhaustion then degrades into slow/shed 503s while the loop stays responsive.
Companion guard for the connections router: test_connections_blocking.py.
"""

import inspect

from backend.api import auth as auth_api
from backend.api import dashboards as dash_api


def test_no_dashboard_handler_runs_on_the_event_loop():
    """Every dashboards handler does sync SQLAlchemy with zero awaits. A single
    `async def` reintroduces the freeze."""
    offenders = [
        route.endpoint.__name__
        for route in dash_api.router.routes
        if inspect.iscoroutinefunction(route.endpoint)
    ]

    assert offenders == [], (
        f"these handlers would block the event loop: {offenders}. "
        "Declare them `def` so Starlette runs them in a threadpool, or make "
        "the blocking part `await asyncio.to_thread(...)`."
    )


def test_the_dashboards_router_actually_has_handlers():
    """Stops the guard above from passing on an empty list."""
    assert len(dash_api.router.routes) >= 5


def test_auth_me_runs_in_threadpool():
    """GET /auth/me is the hottest authed endpoint and does sync DB + sync
    Redis. The auth router keeps legitimately-async handlers (logout,
    delete_account await SSO calls), so guard this one handler, not the router.
    """
    assert not inspect.iscoroutinefunction(auth_api.get_current_user_info), (
        "get_current_user_info must stay plain `def` — as `async def` its sync "
        "db.query/pool checkout blocks the event loop (2026-08-31 outage)."
    )
