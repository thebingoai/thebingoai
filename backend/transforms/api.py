"""Transforms (dbt models) API router (Phase 4)."""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.transforms import DbtModel, DbtRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transforms", tags=["transforms"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class TransformCreate(BaseModel):
    name: str
    sql: str
    materialization: str = "table"  # table | view | incremental
    unique_key: str | None = None
    cron: str | None = None
    owner_scope_kind: str = "user"
    owner_scope_id: str

    @field_validator("materialization")
    @classmethod
    def validate_materialization(cls, v: str) -> str:
        if v not in ("table", "view", "incremental"):
            raise ValueError("materialization must be table, view, or incremental")
        return v

    @field_validator("unique_key")
    @classmethod
    def validate_unique_key(cls, v, info) -> str | None:
        data = info.data
        if data.get("materialization") == "incremental" and not v:
            raise ValueError("unique_key is required for incremental materialization")
        return v


class TransformUpdate(BaseModel):
    name: str | None = None
    sql: str | None = None
    materialization: str | None = None
    unique_key: str | None = None
    cron: str | None = None
    enabled: bool | None = None


class TransformResponse(BaseModel):
    id: str
    name: str
    sql: str
    materialization: str
    unique_key: str | None
    cron: str | None
    owner_scope_kind: str
    owner_scope_id: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    enabled: bool
    created_by_user_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class DbtRunResponse(BaseModel):
    id: str
    owner_scope_kind: str
    owner_scope_id: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    models_run: list[dict] | None
    triggered_by: str
    error_message: str | None
    # manifest_blob is NOT exposed — too large, consumed by Phase 6 lineage only

    model_config = {"from_attributes": True}


class PreviewRequest(BaseModel):
    sql: str
    model_name: str = "preview_model"
    owner_scope_kind: str = "user"
    owner_scope_id: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_transform_for_user(model_id: str, user_id: str, db: Session) -> DbtModel:
    model = db.query(DbtModel).filter(DbtModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Transform not found")
    if model.created_by_user_id != user_id and model.owner_scope_id != user_id:
        raise HTTPException(status_code=404, detail="Transform not found")
    return model


# ---------------------------------------------------------------------------
# POST /api/transforms — create
# ---------------------------------------------------------------------------

@router.post("", response_model=TransformResponse, status_code=status.HTTP_201_CREATED)
async def create_transform(
    body: TransformCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from backend.governance.contract import require as governance_require
    governance_require(
        user=current_user,
        action="create",
        resource={
            "type": "dbt_model",
            "owner_scope_kind": body.owner_scope_kind,
            "owner_scope_id": body.owner_scope_id,
        },
    )

    # Check for duplicate name in scope
    existing = db.query(DbtModel).filter(
        DbtModel.owner_scope_kind == body.owner_scope_kind,
        DbtModel.owner_scope_id == body.owner_scope_id,
        DbtModel.name == body.name,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A transform named {body.name!r} already exists in this scope",
        )

    next_run_at: datetime | None = None
    if body.cron:
        from croniter import croniter
        next_run_at = croniter(body.cron, datetime.now(timezone.utc)).get_next(datetime)

    model = DbtModel(
        id=str(_uuid.uuid4()),
        name=body.name,
        sql=body.sql,
        materialization=body.materialization,
        unique_key=body.unique_key,
        cron=body.cron,
        owner_scope_kind=body.owner_scope_kind,
        owner_scope_id=body.owner_scope_id,
        next_run_at=next_run_at,
        created_by_user_id=current_user.id,
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    from backend.governance.contract import emit_resource_created
    emit_resource_created(
        resource_type="dbt_model",
        resource=model,
        creator_user=current_user,
    )

    # Lazy synth: update the dbt project on disk
    try:
        from backend.data_plane.scope import OwnerScope
        from backend.transforms.project_synth import synthesize_project
        scope = OwnerScope(body.owner_scope_kind, body.owner_scope_id)
        synthesize_project(scope, db)
    except Exception:
        logger.warning("create_transform: project synth failed (non-fatal)", exc_info=True)

    logger.info("Transform %r (id=%s) created by user %s", model.name, model.id, current_user.id)
    return model


# ---------------------------------------------------------------------------
# GET /api/transforms — list
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TransformResponse])
async def list_transforms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(DbtModel)
        .filter(
            (DbtModel.created_by_user_id == current_user.id)
            | (DbtModel.owner_scope_id == current_user.id)
        )
        .order_by(DbtModel.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# GET /api/transforms/{model_id} — single
# ---------------------------------------------------------------------------

@router.get("/{model_id}", response_model=TransformResponse)
async def get_transform(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_transform_for_user(model_id, current_user.id, db)


# ---------------------------------------------------------------------------
# PATCH /api/transforms/{model_id} — update
# ---------------------------------------------------------------------------

@router.patch("/{model_id}", response_model=TransformResponse)
async def update_transform(
    model_id: str,
    body: TransformUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _get_transform_for_user(model_id, current_user.id, db)

    if body.name is not None:
        model.name = body.name
    if body.sql is not None:
        model.sql = body.sql
    if body.materialization is not None:
        model.materialization = body.materialization
    if body.unique_key is not None:
        model.unique_key = body.unique_key
    if body.cron is not None:
        from croniter import croniter
        model.cron = body.cron
        model.next_run_at = croniter(body.cron, datetime.now(timezone.utc)).get_next(datetime)
    if body.enabled is not None:
        model.enabled = body.enabled

    db.commit()
    db.refresh(model)

    # Re-synth project
    try:
        from backend.data_plane.scope import OwnerScope
        from backend.transforms.project_synth import synthesize_project
        scope = OwnerScope(model.owner_scope_kind, model.owner_scope_id)
        synthesize_project(scope, db)
    except Exception:
        logger.warning("update_transform: project synth failed (non-fatal)", exc_info=True)

    return model


# ---------------------------------------------------------------------------
# DELETE /api/transforms/{model_id}
# ---------------------------------------------------------------------------

@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transform(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_transform_for_user(model_id, current_user.id, db)
    from backend.services.resource_lifecycle import delete_dbt_model
    delete_dbt_model(model_id, db)
    db.commit()


# ---------------------------------------------------------------------------
# GET /api/transforms/{model_id}/runs — run history
# ---------------------------------------------------------------------------

@router.get("/{model_id}/runs", response_model=list[DbtRunResponse])
async def get_transform_runs(
    model_id: str,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _get_transform_for_user(model_id, current_user.id, db)

    # Runs are scope-level; filter by scope and check if this model's name appears in models_run
    runs = (
        db.query(DbtRun)
        .filter(
            DbtRun.owner_scope_kind == model.owner_scope_kind,
            DbtRun.owner_scope_id == model.owner_scope_id,
        )
        .order_by(DbtRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return runs


# ---------------------------------------------------------------------------
# POST /api/transforms/{model_id}/run — manual trigger
# ---------------------------------------------------------------------------

@router.post("/{model_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_transform_run(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _get_transform_for_user(model_id, current_user.id, db)
    from backend.transforms.tasks import run_dbt_task

    task = run_dbt_task.delay(
        model.owner_scope_kind,
        model.owner_scope_id,
        [model.id],
        "manual",
    )
    logger.info("Manual dbt trigger for model %s by user %s → task %s", model.id, current_user.id, task.id)
    return {"run_id": task.id, "status": "queued"}


# ---------------------------------------------------------------------------
# POST /api/transforms/preview — compile preview (dbt compile, not run)
# ---------------------------------------------------------------------------

@router.post("/preview", status_code=status.HTTP_200_OK)
async def preview_transform(
    body: PreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Compile a transform SQL via dbt compile and return the compiled SQL."""
    import subprocess
    import tempfile
    import os
    import yaml as _yaml

    # Write a temporary dbt project for compilation
    with tempfile.TemporaryDirectory() as tmpdir:
        models_dir = os.path.join(tmpdir, "models")
        os.makedirs(models_dir)

        # Minimal dbt_project.yml
        with open(os.path.join(tmpdir, "dbt_project.yml"), "w") as f:
            _yaml.dump({
                "name": "preview",
                "version": "1.0.0",
                "config-version": 2,
                "profile": "preview",
                "model-paths": ["models"],
            }, f)

        # Minimal profiles.yml (duckdb in-memory for compile)
        with open(os.path.join(tmpdir, "profiles.yml"), "w") as f:
            _yaml.dump({
                "preview": {
                    "target": "default",
                    "outputs": {"default": {"type": "duckdb", "path": ":memory:", "threads": 1}},
                }
            }, f)

        # Write the model SQL
        with open(os.path.join(models_dir, f"{body.model_name}.sql"), "w") as f:
            f.write(body.sql)

        result = subprocess.run(
            ["dbt", "compile", "--project-dir", tmpdir, "--profiles-dir", tmpdir,
             "--select", body.model_name],
            capture_output=True, text=True, timeout=60,
        )

    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.stderr or result.stdout or "dbt compile failed",
        )

    return {"compiled": True, "stdout": result.stdout[:5000]}
