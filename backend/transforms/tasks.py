"""Celery tasks for dbt scheduling and execution (Phase 4)."""
import logging
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="dispatch_dbt_runs")
def dispatch_dbt_runs():
    """Beat dispatcher: runs every 60s, fires run_dbt_task for due dbt models.

    Gated by new_dbt feature flag per Org scope.
    """
    from croniter import croniter
    from backend.database.session import SessionLocal
    from backend.models.transforms import DbtModel
    from backend.config.feature_flags import enabled as flag_enabled

    db = SessionLocal()
    now = datetime.now(timezone.utc)
    dispatched = 0

    try:
        due = (
            db.query(DbtModel)
            .filter(
                DbtModel.enabled == True,       # noqa: E712
                DbtModel.next_run_at <= now,
                DbtModel.cron.isnot(None),
            )
            .all()
        )

        for model in due:
            try:
                if model.owner_scope_kind == "org":
                    if not flag_enabled(model.owner_scope_id, "new_dbt"):
                        continue

                run_dbt_task.delay(
                    model.owner_scope_kind,
                    model.owner_scope_id,
                    [model.id],
                    "cron",
                )
                dispatched += 1

                if model.cron:
                    model.next_run_at = croniter(model.cron, now).get_next(datetime)

            except Exception as exc:
                logger.error(
                    "dispatch_dbt_runs: failed for model %s: %s", model.id, exc
                )

        if dispatched:
            logger.info("dispatch_dbt_runs: dispatched %d dbt run(s)", dispatched)

        db.commit()

    except Exception:
        logger.exception("dispatch_dbt_runs failed")
        db.rollback()
    finally:
        db.close()


@shared_task(name="run_dbt_task", time_limit=1800)
def run_dbt_task(
    scope_kind: str,
    scope_id: str,
    model_ids: list[str] | None,
    triggered_by: str,
):
    """Execute a dbt run for one scope. Delegates to runner.run_dbt()."""
    from backend.transforms.runner import run_dbt
    from backend.data_plane.scope import OwnerScope

    scope = OwnerScope(scope_kind, scope_id)
    run_id = run_dbt(scope, model_ids=model_ids, triggered_by=triggered_by)
    if run_id:
        logger.info("dbt run %s completed for scope %s/%s", run_id, scope_kind, scope_id)
    return run_id
