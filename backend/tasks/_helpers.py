"""Shared helpers for Celery task implementations."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

from sqlalchemy.orm import Session


@contextmanager
def record_run_failure(
    db: Session,
    run,
    failed_status: str,
    started_at: datetime,
    *,
    logger: logging.Logger,
    task_label: str,
) -> Iterator[None]:
    """Mark a *Run row as failed if the wrapped block raises.

    On exception inside the ``with`` block, sets ``run.status`` to
    ``failed_status``, records the stringified exception in ``run.error``, and
    fills in ``completed_at`` / ``duration_ms`` relative to ``started_at``.
    Commits the update with a rollback fallback. The exception is swallowed —
    Celery sees the task as completed, matching the prior inline behaviour.

    ``run`` may be ``None`` (work failed before the run row was created); in
    that case only the log line is emitted.
    """
    try:
        yield
    except Exception as exc:  # noqa: BLE001 — match existing broad catch
        logger.error("%s failed: %s", task_label, exc)
        if run is None:
            return
        try:
            now = datetime.utcnow()
            run.status = failed_status
            run.error = str(exc)
            run.completed_at = now
            run.duration_ms = int((now - started_at).total_seconds() * 1000)
            db.commit()
        except Exception:  # noqa: BLE001 — match existing broad catch
            db.rollback()
