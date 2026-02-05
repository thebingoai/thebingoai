import httpx
from datetime import datetime
from typing import Any
import logging

logger = logging.getLogger(__name__)

async def send_webhook(
    webhook_url: str,
    job_id: str,
    status: str,
    data: dict[str, Any]
) -> bool:
    """
    Send webhook notification.

    Payload format:
    {
        "event": "upload.completed" | "upload.failed",
        "job_id": "...",
        "timestamp": "2024-01-15T10:30:00Z",
        "data": {...}
    }
    """
    payload = {
        "event": f"upload.{status}",
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": data
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "mdcli-backend/0.1.0"
                }
            )
            success = response.status_code < 400

            if success:
                logger.info(f"Webhook delivered to {webhook_url}")
            else:
                logger.warning(f"Webhook failed: {response.status_code} - {response.text[:100]}")

            return success

    except httpx.TimeoutException:
        logger.error(f"Webhook timeout: {webhook_url}")
        return False
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return False

# Sync version for Celery tasks
def send_webhook_sync(
    webhook_url: str,
    job_id: str,
    status: str,
    data: dict[str, Any]
) -> bool:
    """Synchronous webhook sender for Celery tasks."""
    import asyncio
    return asyncio.run(send_webhook(webhook_url, job_id, status, data))
