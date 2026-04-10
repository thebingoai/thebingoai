"""Celery task for trial account expiration.

Runs hourly via Celery Beat. For each local user with an SSO ID, fetches their
registration date from the SSO admin API, computes trial expiry, and deactivates
expired accounts via SSO.
"""

import logging
from datetime import datetime, timedelta

import httpx
from celery import shared_task

from backend.config import settings
from backend.database.session import SessionLocal
from backend.models.user import User

logger = logging.getLogger(__name__)


def _sso_get_user(sso_id: str) -> dict | None:
    """Fetch user data from the SSO admin API."""
    headers = {"X-API-Key": settings.sso_secret_key}
    try:
        response = httpx.get(
            f"{settings.sso_base_url}/api/v1/users/{sso_id}",
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"SSO get user failed for sso_id={sso_id}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.warning(f"SSO get user error for sso_id={sso_id}: {e}")
        return None


def _sso_deactivate_user(sso_id: str) -> None:
    """Deactivate a user on the SSO side (sets is_active=False)."""
    headers = {"X-API-Key": settings.sso_secret_key}
    try:
        response = httpx.patch(
            f"{settings.sso_base_url}/api/v1/users/{sso_id}/deactivate",
            headers=headers,
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"SSO deactivate failed for sso_id={sso_id}: {e.response.status_code}")
    except Exception as e:
        logger.error(f"SSO deactivate error for sso_id={sso_id}: {e}")


@shared_task(name="expire_trial_accounts")
def expire_trial_accounts():
    """
    Hourly task that checks each user's SSO registration date and deactivates
    accounts whose trial period has elapsed.

    Flow:
    1. Query all local users that have an SSO ID
    2. For each, call SSO admin API to get their registration date (created_at)
    3. Compute trial_expires_at = sso_created_at + TRIAL_PERIOD_DAYS
    4. If expired, call SSO to set is_active=False
    5. On next login, get_current_user() sees is_active=False and blocks the user
    """
    if not settings.sso_secret_key:
        logger.debug("expire_trial_accounts: skipping — no SSO secret key configured (community edition)")
        return

    db = SessionLocal()
    now = datetime.utcnow()

    try:
        users = (
            db.query(User)
            .filter(User.sso_id.isnot(None))
            .all()
        )

        if not users:
            logger.debug("expire_trial_accounts: no SSO-linked users found")
            return

        expired_count = 0

        for user in users:
            sso_data = _sso_get_user(user.sso_id)

            if sso_data is None:
                continue

            sso_created_at = sso_data.get("created_at")
            if not sso_created_at:
                continue

            if isinstance(sso_created_at, str):
                sso_created_at = datetime.fromisoformat(sso_created_at.rstrip("Z"))

            trial_expires_at = sso_created_at + timedelta(days=settings.trial_period_days)

            if now > trial_expires_at:
                expired_count += 1
                logger.info(
                    f"Deactivating expired trial: email={user.email} sso_id={user.sso_id} "
                    f"sso_registered={sso_created_at.isoformat()} "
                    f"trial_expired_at={trial_expires_at.isoformat()}"
                )
                _sso_deactivate_user(user.sso_id)

        if expired_count:
            logger.info(f"expire_trial_accounts: {expired_count} account(s) deactivated")
        else:
            logger.debug("expire_trial_accounts: no expired trial accounts found")

    except Exception as e:
        logger.error(f"expire_trial_accounts failed: {e}")
    finally:
        db.close()
