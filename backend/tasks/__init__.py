"""Celery tasks initialization."""

from backend.tasks.upload_tasks import celery_app, process_upload_async

__all__ = ["celery_app", "process_upload_async"]
