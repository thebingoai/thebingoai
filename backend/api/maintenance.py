"""Maintenance-mode bypass endpoints.

When `MAINTENANCE_MODE=true`, the frontend hides the login UI and routes everyone
to `/maintenance`. Developers can bypass by visiting any URL with
`?maint_bypass=KEY`; the frontend POSTs the key here and, if it matches
`MAINTENANCE_BYPASS_KEY`, we set a short-lived HttpOnly cookie. The cookie value
is just the string `"1"` — its presence is what matters, never its contents —
so a stolen cookie cannot leak the actual key.
"""

import secrets

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from backend.config import settings

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

COOKIE_NAME = "maint_bypass"
COOKIE_MAX_AGE_SECONDS = 24 * 60 * 60  # 24h


class BypassRequest(BaseModel):
    key: str


@router.post("/bypass")
async def grant_bypass(payload: BypassRequest, response: Response):
    """Exchange a valid bypass key for an HttpOnly cookie."""
    if not settings.maintenance_bypass_key:
        # Bypass is intentionally disabled in this environment.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bypass not configured",
        )
    if not secrets.compare_digest(payload.key, settings.maintenance_bypass_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid key",
        )
    response.set_cookie(
        key=COOKIE_NAME,
        value="1",
        httponly=True,
        secure=settings.maintenance_cookie_secure,
        samesite="lax",
        max_age=COOKIE_MAX_AGE_SECONDS,
        path="/",
    )
    return {"ok": True}


@router.delete("/bypass")
async def revoke_bypass(response: Response):
    """Clear the bypass cookie (re-locks the login UI for this browser)."""
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
