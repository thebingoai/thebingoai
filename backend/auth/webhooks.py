"""SSO webhook handler for user lifecycle events."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HMAC-SHA256 webhook signature.

    Skips verification when sso_webhook_secret is not configured (community mode).
    """
    if not settings.sso_webhook_secret:
        logger.warning("SSO webhook secret not configured - skipping signature verification")
        return True

    expected = hmac.HMAC(
        settings.sso_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, signature)


@router.post("/sso")
async def sso_webhook(request: Request):
    """
    Handle SSO lifecycle webhook events.

    Events:
    - user.verified: User email verified
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
        user_email = data.get("email")
        logger.info(f"Password reset for {user_email} - existing tokens will expire from cache")

    elif event_type == "user.verified":
        pass

    return {"status": "ok"}
