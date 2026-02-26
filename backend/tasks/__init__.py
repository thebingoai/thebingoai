"""Celery tasks initialization."""

from backend.tasks.upload_tasks import celery_app, process_upload_async
from backend.tasks.memory_tasks import generate_daily_memories, generate_user_memory
from backend.tasks.heartbeat_tasks import dispatch_heartbeat_jobs, execute_heartbeat_job

__all__ = [
    "celery_app",
    "process_upload_async",
    "generate_daily_memories",
    "generate_user_memory",
    "dispatch_heartbeat_jobs",
    "execute_heartbeat_job",
]
