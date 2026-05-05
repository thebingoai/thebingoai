"""Generic cron-dispatch helper — eliminates copy-paste across dispatchers."""
import logging
from datetime import datetime
from typing import Callable, Type, Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def dispatch_due_rows(
    db: Session,
    *,
    model_cls: Type,
    enabled_field: str,        # attribute name for the "active" boolean
    cron_field: str,           # attribute name for the cron expression
    next_run_field: str,       # attribute name for next_run_at
    dispatch_fn: Callable,     # called with (row) → must enqueue the Celery task
    now: datetime | None = None,
    stagger_seconds: float = 0.0,
) -> int:
    """Dispatch all due rows for one cron-scheduled model.

    Mutates next_run_at on each row. Caller is responsible for committing the
    session after this function returns.

    Returns the count of rows dispatched.
    """
    from croniter import croniter

    if now is None:
        now = datetime.utcnow()

    enabled_col = getattr(model_cls, enabled_field)
    next_run_col = getattr(model_cls, next_run_field)

    due = (
        db.query(model_cls)
        .filter(enabled_col == True, next_run_col <= now)
        .all()
    )

    if not due:
        return 0

    for i, row in enumerate(due):
        try:
            dispatch_fn(row)
            cron_expr = getattr(row, cron_field)
            if cron_expr:
                setattr(row, next_run_field, croniter(cron_expr, now).get_next(datetime))
        except Exception as exc:
            logger.error("dispatch_due_rows: failed for %s id=%s: %s", model_cls.__name__, getattr(row, "id", "?"), exc)

    return len(due)
