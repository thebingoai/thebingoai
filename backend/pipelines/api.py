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
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.pipeline import Pipeline, PipelineRun

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
    mode: str = "full"
    incremental_key: str | None = None
    extraction_config: dict[str, Any] = {}


class PipelineResponse(BaseModel):
    id: str
    name: str
    source_connection_id: int
    owner_scope_kind: str
    owner_scope_id: str
    target_table: str
    cron: str | None
    mode: str
    incremental_key: str | None
    extraction_config: dict[str, Any]
    pipeline_fingerprint: str
    last_run_at: datetime | None
    last_run_status: str | None
    next_run_at: datetime | None
    enabled: bool
    created_by_user_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


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

    # Compute next_run_at from cron
    next_run_at: datetime | None = None
    if body.cron:
        from croniter import croniter
        next_run_at = croniter(body.cron, datetime.now(timezone.utc)).get_next(datetime)

    pipeline = Pipeline(
        id=str(_uuid.uuid4()),
        name=body.name,
        source_connection_id=body.source_connection_id,
        owner_scope_kind=body.owner_scope_kind,
        owner_scope_id=body.owner_scope_id,
        target_table=body.target_table,
        cron=body.cron,
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
    pipelines = (
        db.query(Pipeline)
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
# POST /api/pipelines/{pipeline_id}/run — manual trigger
# ---------------------------------------------------------------------------

@router.post("/{pipeline_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline_run(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
# DELETE /api/pipelines/{pipeline_id}
# ---------------------------------------------------------------------------

@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline_endpoint(
    pipeline_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a pipeline. Metadata + runs removed; materialized output left in place."""
    _get_pipeline_for_user(pipeline_id, current_user.id, db)
    from backend.services.resource_lifecycle import delete_pipeline
    delete_pipeline(pipeline_id, db)
    db.commit()
