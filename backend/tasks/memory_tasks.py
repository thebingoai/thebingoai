"""Celery tasks for memory generation."""

from celery import shared_task
from backend.database.session import SessionLocal
from backend.memory.generator import MemoryGenerator
from backend.models.user import User
from datetime import datetime, timedelta
import logging
import asyncio

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
            try:
                logger.info(f"Generating memory for user {user.id}")
                # Run async function in sync context
                summary = asyncio.run(generator.generate_daily_memory(db, user.id, yesterday))
                logger.info(f"Memory generated: {summary['memory_id']}")
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
        # Run async function in sync context
        summary = asyncio.run(generator.generate_daily_memory(db, user_id, date))
        return summary
    finally:
        db.close()
