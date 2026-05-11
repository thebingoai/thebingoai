"""Postgres-backed dlt pipeline state store (P2.2).

dlt's incremental cursors are stored here instead of at the data destination,
so state is multi-pod-safe and never user-visible.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> Any:
    """Fallback JSON encoder for types JSONB rejects.

    dlt's state dict can contain datetime/date (incremental cursors,
    `last_run_at` markers). PostgreSQL's JSONB column rejects them and the
    psycopg adapter raises ``TypeError: Object of type DateTime is not JSON
    serializable``, which strands the run row at ``status='running'``.
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _to_jsonb_safe(state_blob: dict) -> dict:
    """Round-trip the state blob through JSON to coerce datetime → string."""
    return json.loads(json.dumps(state_blob, default=_json_default))


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
    safe_blob = _to_jsonb_safe(state_blob)
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
            state_blob=safe_blob,
            version=1,
            updated_at=now,
        )
        db.add(row)
    else:
        row.state_blob = safe_blob
        row.version += 1
        row.updated_at = now
    db.flush()
