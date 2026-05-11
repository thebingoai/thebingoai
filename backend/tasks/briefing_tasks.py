"""Celery task wrapper for briefing_runner."""

import asyncio
import logging
from celery import shared_task

from backend.services import briefing_runner

logger = logging.getLogger(__name__)


@shared_task(name="generate_briefing", time_limit=600)
def generate_briefing(briefing_id: int) -> None:
    """Generate a briefing in a Celery worker."""
    try:
        asyncio.run(briefing_runner.run(briefing_id))
    except Exception as e:
        logger.exception("generate_briefing task failed for briefing_id=%s: %s", briefing_id, e)
        raise
