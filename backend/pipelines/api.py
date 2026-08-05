"""Pipeline API router (Phase 2)."""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user, forbid_viewer
from backend.models.user import User
from backend.models.pipeline import Pipeline, PipelineRun
from backend.utils.cron import compute_next_run, is_valid_timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class PipelineCreate(BaseModel):
    name: str
    source_connection_id: int
    owner_scope_kind: str = "user"
    owner_scope_id: str
    target_table: str
    cron: str | None = None
    timezone: str | None = None
    mode: str = "full"
    incremental_key: str | None = None
    extraction_config: dict[str, Any] = {}


class ScheduleResponse(BaseModel):
    """A new-model `PipelineSchedule` row (cadence + per-table specs)."""
    id: str
    name: str | None
    cron: str | None
    timezone: str
    enabled: bool
    next_run_at: datetime | None
    tables: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class PipelineResponse(BaseModel):
    id: str
    name: str
    source_connection_id: int
    owner_scope_kind: str
    owner_scope_id: str
    target_table: str | None
    cron: str | None
    timezone: str
    mode: str
    incremental_key: str | None
    unique_key: list[str] | None
    extraction_config: dict[str, Any]
    pipeline_fingerprint: str
    last_run_at: datetime | None
    last_run_status: str | None
    next_run_at: datetime | None
    enabled: bool
    created_by_user_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schedules: list[ScheduleResponse] = []

    model_config = {"from_attributes": True}


class ScheduleUpdate(BaseModel):
    """Partial update for a new-model schedule. `tables` is a list of source
    table names; specs are re-derived server-side."""
    cron: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    tables: list[str] | None = None


class PipelineUpdate(BaseModel):
    """Fields the UI is allowed to mutate on an existing pipeline.

    Schedule (`cron`/`timezone`), `enabled` toggle, `name`, and the
    Phase 3 ingest-shape overrides: `mode` (full/incremental) and
    `incremental_key` (cursor column). Changing source tables still requires
    delete + recreate so the old fingerprint's Parquet stays untouched.

    `incremental_key` uses an explicit empty-string sentinel for "clear the
    cursor" because Pydantic can't distinguish `None` (unset) from `None`
    (explicit null) in a JSON PATCH body.
    """
    name: str | None = None
    cron: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    mode: str | None = None
    incremental_key: str | None = None


class LoadHistoryRequest(BaseModel):
    """Body of `POST /api/pipelines/{id}/load-history`.

    `since` is an ISO-8601 timestamp (UTC by convention). The runner forwards
    it to `sql_dlt_source` as the dlt incremental cursor's `initial_value`,
    overriding any persisted state for this single run.
    """
    since: datetime


class PipelineRunResponse(BaseModel):
    id: str
    pipeline_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    rows_written: int | None
    bytes_written: int | None
    error_message: str | None
    triggered_by: str
    triggered_by_user_id: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_pipeline_for_user(pipeline_id: str, user_id: str, db: Session) -> Pipeline:
    """Fetch a pipeline owned by (or accessible to) the requesting user."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    # Ownership check: pipeline belongs to the user directly OR the user created it
    if pipeline.created_by_user_id != user_id and pipeline.owner_scope_id != user_id:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


# ---------------------------------------------------------------------------
# POST /api/pipelines — create
# ---------------------------------------------------------------------------

@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    body: PipelineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Create a new pipeline.

    Validates extraction_config against the connector's model (P2.1),
    deduplicates by fingerprint within the owner scope, and sets next_run_at
    from the cron expression when provided.
    """
    from backend.governance.contract import require as governance_require
    governance_require(
        user=current_user,
        action="create",
        resource={
            "type": "pipeline",
            "owner_scope_kind": body.owner_scope_kind,
            "owner_scope_id": body.owner_scope_id,
        },
    )

    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector_registration
    from backend.pipelines.runner import compute_pipeline_fingerprint

    # Verify the source connection exists and is accessible to the user
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == body.source_connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source connection not found",
        )

    reg = get_connector_registration(connection.db_type)

    # P2.1: validate extraction_config against the connector's model if present
    if reg and reg.extraction_config_model is not None:
        try:
            reg.extraction_config_model(**body.extraction_config)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid extraction_config: {exc}",
            )

    # Compute pipeline fingerprint
    conn_fingerprint = (reg.fingerprint(connection) if (reg and reg.fingerprint) else None) or ""
    fingerprint = compute_pipeline_fingerprint(conn_fingerprint, body.extraction_config)

    # Dedup check: same owner scope + fingerprint → 409
    existing = db.query(Pipeline).filter(
        Pipeline.owner_scope_kind == body.owner_scope_kind,
        Pipeline.owner_scope_id == body.owner_scope_id,
        Pipeline.pipeline_fingerprint == fingerprint,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A pipeline with this configuration already exists: id={existing.id}",
        )

    # Validate timezone
    tz_name = body.timezone or "UTC"
    if tz_name != "UTC" and not is_valid_timezone(tz_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown IANA timezone: {tz_name}",
        )

    # Compute next_run_at from cron, evaluated in the requested timezone
    next_run_at: datetime | None = None
    if body.cron:
        next_run_at = compute_next_run(body.cron, tz_name)

    pipeline = Pipeline(
        id=str(_uuid.uuid4()),
        name=body.name,
        source_connection_id=body.source_connection_id,
        owner_scope_kind=body.owner_scope_kind,
        owner_scope_id=body.owner_scope_id,
        target_table=body.target_table,
        cron=body.cron,
        timezone=tz_name,
        mode=body.mode,
        incremental_key=body.incremental_key,
        extraction_config=body.extraction_config,
        pipeline_fingerprint=fingerprint,
        next_run_at=next_run_at,
        created_by_user_id=current_user.id,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)

    from backend.governance.contract import emit_resource_created
    emit_resource_created(
        resource_type="pipeline",
        resource=pipeline,
        creator_user=current_user,
    )

    logger.info(
        "Pipeline %r (id=%s) created by user %s",
        pipeline.name, pipeline.id, current_user.id,
    )
    return pipeline


# ---------------------------------------------------------------------------
# GET /api/pipelines — list
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PipelineResponse])
async def list_pipelines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pipelines for the requesting user (created by them or scoped to them)."""
    from sqlalchemy.orm import selectinload
    pipelines = (
        db.query(Pipeline)
        .options(selectinload(Pipeline.schedules))
        .filter(
            (Pipeline.created_by_user_id == current_user.id)
            | (Pipeline.owner_scope_id == current_user.id)
        )
        .order_by(Pipeline.created_at.desc())
        .all()
    )
    return pipelines


# ---------------------------------------------------------------------------
# GET /api/pipelines/{pipeline_id} — get single
# ---------------------------------------------------------------------------

@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single pipeline by ID."""
    return _get_pipeline_for_user(pipeline_id, current_user.id, db)


# ---------------------------------------------------------------------------
# GET /api/pipelines/{pipeline_id}/runs — run history
# ---------------------------------------------------------------------------

@router.get("/{pipeline_id}/runs", response_model=list[PipelineRunResponse])
async def get_pipeline_runs(
    pipeline_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List recent runs for a pipeline, newest first."""
    _get_pipeline_for_user(pipeline_id, current_user.id, db)

    runs = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return runs


# ---------------------------------------------------------------------------
# PATCH /api/pipelines/{pipeline_id} — partial update
# ---------------------------------------------------------------------------

@router.patch("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Partial update — schedule, name, and enabled toggle only.

    Recomputes `next_run_at` when cron / timezone changes, or when the pipeline
    is re-enabled with an existing cron.
    """
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)

    if body.timezone is not None and body.timezone != "UTC" and not is_valid_timezone(body.timezone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown IANA timezone: {body.timezone}",
        )

    if body.mode is not None and body.mode not in ("full", "incremental"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"mode must be 'full' or 'incremental' (got: {body.mode!r})",
        )

    # `mode='incremental'` requires a cursor column. Use the body value when
    # both fields arrive in the same PATCH; otherwise the existing pipeline value.
    effective_mode = body.mode if body.mode is not None else pipeline.mode
    effective_inc_key = (
        body.incremental_key if body.incremental_key is not None else pipeline.incremental_key
    )
    if effective_mode == "incremental" and not effective_inc_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="incremental mode requires a non-empty incremental_key",
        )

    for field in ("name", "cron", "timezone", "enabled", "mode", "incremental_key"):
        val = getattr(body, field)
        if val is not None:
            # Empty string on incremental_key explicitly clears the cursor.
            if field == "incremental_key" and val == "":
                setattr(pipeline, field, None)
            else:
                setattr(pipeline, field, val)

    if body.cron is not None or body.timezone is not None or body.enabled is True:
        if pipeline.cron and pipeline.enabled:
            pipeline.next_run_at = compute_next_run(
                pipeline.cron, pipeline.timezone or "UTC",
            )
        else:
            pipeline.next_run_at = None

    db.commit()
    db.refresh(pipeline)
    logger.info("Pipeline %s updated by user %s", pipeline.id, current_user.id)
    return pipeline


# ---------------------------------------------------------------------------
# PATCH /api/pipelines/{pipeline_id}/schedules/{schedule_id} — edit a schedule
# ---------------------------------------------------------------------------

@router.patch("/{pipeline_id}/schedules/{schedule_id}", response_model=PipelineResponse)
async def update_schedule_endpoint(
    pipeline_id: str,
    schedule_id: str,
    body: ScheduleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Edit a new-model schedule (cron / timezone / enabled / tables)."""
    from sqlalchemy.orm import selectinload
    from backend.models.pipeline import PipelineSchedule
    from backend.pipelines.schedule_ops import update_schedule

    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)
    schedule = db.query(PipelineSchedule).filter(
        PipelineSchedule.id == schedule_id,
        PipelineSchedule.pipeline_id == pipeline_id,
    ).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    fields = body.model_dump(exclude_unset=True)
    try:
        update_schedule(pipeline, schedule, db, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()

    pipeline = (
        db.query(Pipeline)
        .options(selectinload(Pipeline.schedules))
        .filter(Pipeline.id == pipeline_id)
        .first()
    )
    logger.info("Schedule %s updated by user %s", schedule_id, current_user.id)
    return pipeline


# ---------------------------------------------------------------------------
# POST /api/pipelines/{pipeline_id}/run — manual trigger
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline_run(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Manually trigger a pipeline run. Dispatches via Celery."""
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)

    from backend.pipelines.tasks import run_pipeline_task

    task = run_pipeline_task.delay(pipeline.id, "manual", current_user.id)
    logger.info(
        "Manual trigger for pipeline %s by user %s → task %s",
        pipeline.id, current_user.id, task.id,
    )
    return {"run_id": task.id, "status": "queued"}


# ---------------------------------------------------------------------------
# POST /api/pipelines/{pipeline_id}/redetect-watermark
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/redetect-watermark", response_model=PipelineResponse)
async def redetect_watermark(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Re-run the watermark classifier for the pipeline's source table.

    Useful after schema changes (new `updated_at` column added, etc.) so the
    UI can refresh the cursor pick without delete + recreate. Persists the
    pick, flips `mode` to 'incremental' on success / 'full' on miss.
    """
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)
    src_tables = (pipeline.extraction_config or {}).get("tables") or []
    if not src_tables:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Pipeline has no source tables in extraction_config",
        )
    table = src_tables[0]

    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import (
        get_connector_for_connection, get_connector_registration,
    )
    from backend.services.watermark_classifier import resolve_watermark

    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == pipeline.source_connection_id,
    ).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Source connection missing")
    reg = get_connector_registration(conn.db_type)
    try:
        with get_connector_for_connection(conn, db) as connector:
            schema_obj = connector.get_table_schema(table, schema=None)
            cols = list(getattr(schema_obj, "columns", []) or [])
            picks = resolve_watermark(reg, connector, [table], {table: cols})
    except Exception as e:
        logger.warning("redetect_watermark failed for pipeline %s: %s", pipeline.id, e)
        raise HTTPException(status_code=502, detail=f"Watermark detection failed: {e}")

    new_key = picks.get(table)
    pipeline.incremental_key = new_key
    pipeline.mode = "incremental" if new_key else "full"
    db.commit()
    db.refresh(pipeline)
    logger.info(
        "Pipeline %s watermark re-detected by user %s → key=%r, mode=%s",
        pipeline.id, current_user.id, new_key, pipeline.mode,
    )
    return pipeline


# ---------------------------------------------------------------------------
# POST /api/pipelines/{pipeline_id}/load-history
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/load-history", status_code=status.HTTP_202_ACCEPTED)
async def load_history(
    pipeline_id: str,
    body: LoadHistoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Backfill pre-T-1 history: queue a one-shot run with `backfill_since`.

    The runner forwards `since` to dlt's incremental cursor as `initial_value`,
    so the next dlt extract pulls rows from `cursor_col >= since`. Merge
    dedup via `unique_key` keeps subsequent normal cron runs idempotent.
    """
    pipeline = _get_pipeline_for_user(pipeline_id, current_user.id, db)
    if pipeline.mode != "incremental" or not pipeline.incremental_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Load-history requires an incremental pipeline with a configured incremental_key",
        )

    from backend.pipelines.tasks import run_pipeline_task

    since_iso = body.since.astimezone(timezone.utc).isoformat() if body.since.tzinfo else body.since.isoformat()
    task = run_pipeline_task.delay(pipeline.id, "manual-backfill", current_user.id, since_iso)
    logger.info(
        "load-history triggered for pipeline %s by user %s since=%s → task %s",
        pipeline.id, current_user.id, since_iso, task.id,
    )
    return {"run_id": task.id, "status": "queued", "since": since_iso}


# ---------------------------------------------------------------------------
# DELETE /api/pipelines/{pipeline_id}
# ---------------------------------------------------------------------------

@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_endpoint(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _viewer=Depends(forbid_viewer),
):
    """Delete a pipeline. Metadata + runs removed; materialized output left in place."""
    _get_pipeline_for_user(pipeline_id, current_user.id, db)
    from backend.services.resource_lifecycle import delete_pipeline
    delete_pipeline(pipeline_id, db)
    db.commit()


