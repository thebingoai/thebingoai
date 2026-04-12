"""Celery tasks for memory generation."""

from celery import shared_task
from backend.database.session import SessionLocal
from backend.memory.generator import MemoryGenerator
from backend.models.user import User
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name="generate_daily_memories")
def generate_daily_memories():
    """
    Celery task to generate daily memories for all users.

    Runs daily at midnight (configured in Celery beat schedule).
    """
    db = SessionLocal()
    generator = MemoryGenerator()

    try:
        # Get all users
        users = db.query(User).all()
        yesterday = datetime.utcnow() - timedelta(days=1)

        for user in users:
            prefs = user.preferences or {}
            if not prefs.get("memory_enabled", True):
                logger.info(f"Skipping memory generation for user {user.id} (memory_enabled=False)")
                continue
            try:
                logger.info(f"Generating memory for user {user.id}")
                # --- Credit context (bingo-credits plugin) ---
                _credit_mgr = None
                try:
                    from backend.plugins.loader import get_loaded_plugins
                    if "bingo-credits" in get_loaded_plugins():
                        from bingo_credits.credit_context import CreditContextManager
                        _credit_mgr = CreditContextManager(
                            db=db,
                            user_id=user.id,
                            title=f"Memory generation: {yesterday.date()}",
                            provider_name=None,
                            conversation_id=None,
                            block_on_insufficient=False,
                        )
                except Exception as _credit_err:
                    logger.warning("Credit context setup failed for memory generation: %s", _credit_err)
                    _credit_mgr = None
                from contextlib import nullcontext
                # Use sync wrapper for Celery task
                with (_credit_mgr if _credit_mgr is not None else nullcontext()):
                    summary = generator.generate_daily_memory_sync(db, user.id, yesterday)
                if "memory_id" in summary:
                    logger.info(f"Memory generated: {summary['memory_id']}")
                else:
                    logger.info(f"No conversations found for user {user.id} on {yesterday.date()}")
            except Exception as e:
                logger.error(f"Failed to generate memory for user {user.id}: {str(e)}")

    finally:
        db.close()


@shared_task(name="generate_user_memory")
def generate_user_memory(user_id: str, date_str: str):
    """
    Generate memory for a specific user and date.

    Args:
        user_id: User ID
        date_str: Date string in ISO format

    Returns:
        Memory summary dictionary
    """
    db = SessionLocal()
    generator = MemoryGenerator()

    try:
        date = datetime.fromisoformat(date_str)
        # --- Credit context (bingo-credits plugin) ---
        _credit_mgr = None
        try:
            from backend.plugins.loader import get_loaded_plugins
            if "bingo-credits" in get_loaded_plugins():
                from bingo_credits.credit_context import CreditContextManager
                _credit_mgr = CreditContextManager(
                    db=db,
                    user_id=user_id,
                    title=f"Memory generation: {date_str}",
                    provider_name=None,
                    conversation_id=None,
                    block_on_insufficient=False,
                )
        except Exception as _credit_err:
            logger.warning("Credit context setup failed for memory generation: %s", _credit_err)
            _credit_mgr = None
        from contextlib import nullcontext
        # Use sync wrapper for Celery task
        with (_credit_mgr if _credit_mgr is not None else nullcontext()):
            summary = generator.generate_daily_memory_sync(db, user_id, date)
        return summary
    finally:
        db.close()
