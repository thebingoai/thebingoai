"""Background watermark refinement (decision #9 of the connector→plane plan).

`_apply_mysql_t1_schedule` runs the deterministic matcher synchronously at
connect time so the create-connection response stays snappy. This module hosts
the LLM refinement step, fired asynchronously from `api/connections.py` after
materialization commits.

When the watermark classifier env knobs (``WATERMARK_CLASSIFIER_PROVIDER`` and
``WATERMARK_CLASSIFIER_MODEL``) are unset, this task is a no-op — the LLM call
short-circuits inside `classify_connection`. When set, the task batches all
single-table pipelines for one connection in a single LLM request, then
applies any **high-confidence** column choice that differs from what the
deterministic pass already wrote.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="refine_watermarks_task", time_limit=300)
def refine_watermarks_task(connection_id: int, pipeline_ids: list[str]) -> dict:
    """Re-classify watermarks via the LLM batched classifier; apply refinements.

    Returns a small summary dict for log/monitor visibility.
    Per-pipeline failures are swallowed — refinement is best-effort.
    """
    from backend.config import settings
    from backend.database.session import SessionLocal
    from backend.models.database_connection import DatabaseConnection
    from backend.models.pipeline import Pipeline
    from backend.connectors.factory import get_connector_for_connection
    from backend.services.watermark_classifier import classify_connection

    if not (
        getattr(settings, "watermark_classifier_provider", "")
        and getattr(settings, "watermark_classifier_model", "")
    ):
        return {"status": "skipped", "reason": "llm_not_configured"}

    db = SessionLocal()
    try:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
        ).first()
        if not connection:
            return {"status": "skipped", "reason": "connection_missing"}

        pipelines = (
            db.query(Pipeline)
            .filter(Pipeline.id.in_(pipeline_ids), Pipeline.source_connection_id == connection_id)
            .all()
        )
        if not pipelines:
            return {"status": "skipped", "reason": "no_pipelines"}

        # Map pipeline → table for the single-table case; multi-table pipelines
        # are skipped (matches the sync path's gate).
        pipe_by_table: dict[str, Pipeline] = {}
        for p in pipelines:
            tables = (p.extraction_config or {}).get("tables") or []
            if len(tables) == 1:
                pipe_by_table[tables[0]] = p

        if not pipe_by_table:
            return {"status": "skipped", "reason": "no_single_table_pipelines"}

        try:
            connector = get_connector_for_connection(connection, db)
        except Exception:
            logger.warning(
                "refine_watermarks_task: cannot open connector for connection %s",
                connection_id, exc_info=True,
            )
            return {"status": "skipped", "reason": "connector_open_failed"}

        table_schemas: dict[str, list[dict]] = {}
        try:
            for table in pipe_by_table:
                try:
                    schema_obj = connector.get_table_schema(table, schema=None)
                    table_schemas[table] = list(getattr(schema_obj, "columns", []) or [])
                except Exception:
                    logger.debug(
                        "refine_watermarks_task: schema fetch failed for %s", table, exc_info=True,
                    )
        finally:
            close = getattr(connector, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

        if not table_schemas:
            return {"status": "skipped", "reason": "no_schema"}

        try:
            llm_map = classify_connection(table_schemas)
        except Exception:
            logger.warning(
                "refine_watermarks_task: classifier crashed for connection %s",
                connection_id, exc_info=True,
            )
            return {"status": "skipped", "reason": "classifier_failed"}

        # Mirror the sync path's T-n lower-bound logic so promotion behaves
        # consistently regardless of whether the LLM ran sync or async.
        lookback_days = int(getattr(settings, "first_ingest_lookback_days", 0) or 0)
        if lookback_days > 0:
            initial_dt = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
        else:
            initial_dt = None

        updated = 0
        for table, suggested in llm_map.items():
            p = pipe_by_table.get(table)
            if p is None:
                continue
            current = p.incremental_key
            if suggested == current:
                continue  # no change — deterministic already matched

            new_cfg = dict(p.extraction_config or {})
            if suggested:
                p.mode = "incremental"
                p.incremental_key = suggested
                new_cfg["incremental_key"] = suggested
                if initial_dt is not None:
                    # Seed only if the sync path didn't already (preserve
                    # whatever lower bound it computed).
                    new_cfg.setdefault("initial_value", initial_dt.isoformat())
                else:
                    new_cfg.pop("initial_value", None)
            else:
                p.mode = "full"
                p.incremental_key = None
                new_cfg.pop("incremental_key", None)
                new_cfg.pop("initial_value", None)
            p.extraction_config = new_cfg
            updated += 1

        if updated:
            db.commit()
            logger.info(
                "refine_watermarks_task: refined %d/%d pipeline(s) for connection %s",
                updated, len(pipe_by_table), connection_id,
            )
        return {
            "status": "ok",
            "connection_id": connection_id,
            "considered": len(pipe_by_table),
            "updated": updated,
        }
    finally:
        db.close()
