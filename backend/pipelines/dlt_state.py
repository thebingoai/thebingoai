"""Postgres-backed dlt pipeline state store (P2.2).

dlt's incremental cursors are stored here instead of at the data destination,
so state is multi-pod-safe and never user-visible.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def get_state(pipeline_id: str, db) -> dict:
    """Return the current state blob for *pipeline_id*, or {} if none."""
    from backend.models.pipeline import DltPipelineState
    row = db.query(DltPipelineState).filter(
        DltPipelineState.pipeline_id == pipeline_id
    ).first()
    if row is None:
        return {}
    return row.state_blob or {}


def set_state(pipeline_id: str, state_blob: dict, db, *, owner_scope_kind: str, owner_scope_id: str) -> None:
    """Upsert the state blob for *pipeline_id* with an optimistic version bump."""
    from backend.models.pipeline import DltPipelineState
    row = db.query(DltPipelineState).filter(
        DltPipelineState.pipeline_id == pipeline_id
    ).first()
    now = datetime.now(timezone.utc)
    if row is None:
        import uuid
        row = DltPipelineState(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline_id,
            owner_scope_kind=owner_scope_kind,
            owner_scope_id=owner_scope_id,
            state_blob=state_blob,
            version=1,
            updated_at=now,
        )
        db.add(row)
    else:
        row.state_blob = state_blob
        row.version += 1
        row.updated_at = now
    db.flush()
