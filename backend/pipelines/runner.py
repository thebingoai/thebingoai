"""Pipeline runner — the core execute-a-Pipeline logic (Phase 2)."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

PIPELINE_LOCK_TTL = 1800  # 30 minutes


def compute_pipeline_fingerprint(connection_fingerprint: str | None, extraction_config: dict) -> str:
    """sha256(conn_fingerprint | canonical_json(extraction_config))."""
    canonical = json.dumps(extraction_config, sort_keys=True, separators=(",", ":"))
    raw = f"{connection_fingerprint or ''}|{canonical}"
    return hashlib.sha256(raw.encode()).hexdigest()


def run_pipeline(
    pipeline_id: str,
    triggered_by: Literal["cron", "manual", "api"],
    triggered_by_user_id: str | None = None,
) -> str:
    """Execute a Pipeline; return the new pipeline_run_id.

    Steps:
    1. Acquire Redis lock keyed pipeline:run:{pipeline_id}. Skip if held.
    2. Insert PipelineRun(status='running').
    3. Enter system_context(reason='pipeline.run', scope=...).
    4. Call connector's dlt_source_for(connection, extraction_config).
    5. Build dlt destination wrapping DataPlane.
    6. dlt.run(source, destination).
    7. Update Pipeline + PipelineRun to terminal status.
    8. Publish lineage:invalidate to Redis pub/sub.
    9. Publish pipeline.run.failed event if failed.
    10. Chain profile_pipeline_output Celery task on success.
    11. Release lock.
    """
    import uuid
    import redis as syncredis
    from datetime import datetime, timezone

    from backend.config import settings
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline, PipelineRun
    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector_registration
    from backend.auth.system_context import system_context
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane

    redis_client = syncredis.from_url(settings.redis_url)
    lock_key = f"pipeline:run:{pipeline_id}"
    lock = redis_client.lock(lock_key, timeout=PIPELINE_LOCK_TTL)

    if not lock.acquire(blocking=False):
        logger.info("Pipeline %s already running (Redis lock held), skipping", pipeline_id)
        return ""

    db = SessionLocal()
    run_id = str(uuid.uuid4())
    run = None

    try:
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            logger.warning("run_pipeline: pipeline %s not found", pipeline_id)
            return ""

        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == pipeline.source_connection_id
        ).first()
        if not connection:
            raise RuntimeError(f"Source connection {pipeline.source_connection_id} not found")

        scope = OwnerScope(pipeline.owner_scope_kind, pipeline.owner_scope_id)
        plane = get_default_plane(scope, db)

        # Insert running run record
        started_at = datetime.now(timezone.utc)
        run = PipelineRun(
            id=run_id,
            pipeline_id=pipeline_id,
            started_at=started_at,
            status="running",
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
        )
        db.add(run)
        pipeline.last_run_status = "running"
        db.commit()

        error_message = None
        rows_written = 0
        bytes_written = 0

        try:
            with system_context(reason="pipeline.run", scope=scope):
                # Get connector registration to find dlt_source_for
                reg = get_connector_registration(connection.db_type)
                if reg is None:
                    raise RuntimeError(f"No connector registration for db_type={connection.db_type!r}")

                connector_cls = reg.connector_class

                # Resolve dlt_source_for: prefer the registration field (new shape),
                # fall back to a connector_class attribute (legacy shape) for plugins
                # that haven't been ported to the new template scaffold yet.
                source_fn = reg.dlt_source_for
                if source_fn is None and hasattr(connector_cls, "dlt_source_for"):
                    source_fn = connector_cls.dlt_source_for
                if source_fn is None:
                    raise RuntimeError(
                        f"Connector {connection.db_type!r} does not implement dlt_source_for — "
                        "cannot run as a Pipeline"
                    )

                # pre_run hook (token refresh, auth setup)
                if hasattr(connector_cls, "pre_run"):
                    connector_cls.pre_run(connection)

                # Build dlt source
                extraction_config = pipeline.extraction_config or {}
                source = source_fn(connection, extraction_config)

                # Build dlt destination wrapping DataPlane
                from backend.pipelines.dlt_destination import make_dataplane_destination
                destination = make_dataplane_destination(plane, scope, pipeline.target_table)

                # Run dlt
                import dlt as _dlt
                dlt_pipeline = _dlt.pipeline(
                    pipeline_name=f"bingo_{pipeline_id[:8]}",
                    destination=destination,
                )
                write_disposition = "replace" if pipeline.mode == "full" else "merge"
                load_info = dlt_pipeline.run(
                    source,
                    table_name=pipeline.target_table,
                    write_disposition=write_disposition,
                    primary_key=pipeline.incremental_key or None,
                )

                # Collect metrics
                for load_pkg in (load_info.load_packages or []):
                    for job in (load_pkg.jobs.get("completed_jobs") or []):
                        rows_written += getattr(job, "file_size", 0) or 0  # approximate
                        bytes_written += getattr(job, "file_size", 0) or 0

                # Persist dlt incremental state. Isolate this in its own
                # try/except + rollback so a serialization gap (e.g. an
                # unexpected non-JSON type in dlt's state dict) cannot strand
                # the session and prevent the terminal run-status commit below.
                from backend.pipelines.dlt_state import set_state as _set_state
                raw_state = dlt_pipeline.state or {}
                try:
                    _set_state(
                        pipeline_id,
                        raw_state,
                        db,
                        owner_scope_kind=pipeline.owner_scope_kind,
                        owner_scope_id=pipeline.owner_scope_id,
                    )
                except Exception:
                    logger.exception(
                        "Pipeline %s run %s: failed to persist dlt state; continuing with run-status update",
                        pipeline_id, run_id,
                    )
                    db.rollback()

        except Exception as exc:
            error_message = str(exc)[:2000]
            logger.exception("Pipeline %s run %s failed", pipeline_id, run_id)

        # Update terminal status
        finished_at = datetime.now(timezone.utc)
        status = "failed" if error_message else "success"

        run.status = status
        run.finished_at = finished_at
        run.error_message = error_message
        run.rows_written = rows_written or None
        run.bytes_written = bytes_written or None

        pipeline.last_run_status = status
        pipeline.last_run_at = finished_at

        # Advance next_run_at for cron pipelines
        if pipeline.cron:
            from croniter import croniter
            pipeline.next_run_at = croniter(pipeline.cron, finished_at).get_next(datetime)

        db.commit()

        # Publish lineage:invalidate
        try:
            redis_client.publish("lineage:invalidate", json.dumps({
                "pipeline_id": pipeline_id,
                "scope_kind": pipeline.owner_scope_kind,
                "scope_id": pipeline.owner_scope_id,
            }))
        except Exception:
            logger.warning("Failed to publish lineage:invalidate for pipeline %s", pipeline_id)

        # Publish pipeline.run.failed notification event
        if status == "failed":
            try:
                from backend.notifications import publish
                publish({
                    "event_type": "pipeline.run.failed",
                    "scope": {"kind": pipeline.owner_scope_kind, "id": pipeline.owner_scope_id},
                    "resource_type": "pipeline",
                    "resource_id": pipeline_id,
                    "name": pipeline.name,
                    "run_id": run_id,
                    "error_message": error_message,
                })
            except Exception:
                logger.warning("Failed to publish pipeline.run.failed for pipeline %s", pipeline_id)

        # Chain profiling task on success
        if status == "success":
            try:
                from backend.tasks.profiling_tasks import profile_pipeline_output
                profile_pipeline_output.delay(pipeline_id, run_id)
            except Exception:
                logger.warning("Failed to chain profile_pipeline_output for pipeline %s", pipeline_id)

        return run_id

    except Exception as exc:
        logger.exception("run_pipeline outer error for pipeline %s", pipeline_id)
        if run is not None:
            try:
                run.status = "failed"
                run.error_message = str(exc)[:2000]
                run.finished_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
        return run_id or ""

    finally:
        db.close()
        try:
            lock.release()
        except Exception:
            pass
        try:
            redis_client.close()
        except Exception:
            pass
