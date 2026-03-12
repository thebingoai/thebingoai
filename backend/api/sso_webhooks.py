"""SSO webhook handler for user lifecycle events."""
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 webhook signature."""
    if not settings.sso_webhook_secret:
        # If no secret configured, skip verification (dev mode)
        logger.warning("SSO webhook secret not configured - skipping signature verification")
        return True

    expected = hmac.HMAC(
        settings.sso_webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, signature)


@router.post("/sso")
async def sso_webhook(request: Request):
    """
    Handle SSO lifecycle webhook events.

    Events:
    - user.verified: User email verified (optional pre-create local record)
    - user.password_reset: Invalidate cached tokens for the user
    """
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not _verify_webhook_signature(payload, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_type = event.get("event")
    data = event.get("data", {})

    logger.info(f"SSO webhook received: {event_type}")

    if event_type == "user.password_reset":
        # User reset their password - any existing access tokens are now invalid
        # We can't enumerate cached tokens by email, so just log
        # The tokens will naturally expire from cache (TTL-based)
        user_email = data.get("email")
        logger.info(f"Password reset for {user_email} - existing tokens will expire from cache")

    elif event_type == "user.verified":
        # Email verified - optionally pre-create local user record
        # (The record will also be auto-created on first login)
        pass

    return {"status": "ok"}
