"""Materialize plugin-shipped pipeline + transform templates into DB rows.

A plugin can declare `pipeline_templates` and `transform_templates` on its
`ConnectorRegistration`. This service turns those declarations into regular
`pipelines` / `dbt_models` rows for a given connection.

Called from two places:
- `api/connections.py:create_connection` — when a new connection is created.
- `plugins/loader.py` — at startup, to backfill existing connections that
  pre-date a plugin's templates.

Idempotency is guaranteed by the existing unique constraints
(`uq_pipeline_scope_fingerprint`, `uq_dbt_model_scope_name`): the function
SELECTs first and skips on conflict, so it is safe to call repeatedly.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.data_plane.scope import OwnerScope
from backend.models.pipeline import Pipeline
from backend.models.transforms import DbtModel
from backend.pipelines.runner import compute_pipeline_fingerprint
from backend.plugins.base import ConnectorRegistration, PipelineTemplate, TransformTemplate

logger = logging.getLogger(__name__)


def _try_insert(db: Session, row) -> bool:
    """Insert `row` inside a SAVEPOINT. Return True on success, False if a
    unique constraint fired (another process won the race — that's success
    from our perspective: the row exists).
    """
    sp = db.begin_nested()
    try:
        db.add(row)
        db.flush()
    except IntegrityError:
        sp.rollback()
        return False
    return True


def _resolve_extraction_config(template: PipelineTemplate, connection) -> dict:
    cfg = template.extraction_config
    return cfg(connection) if callable(cfg) else dict(cfg)


def _resolve_target_table(template: PipelineTemplate, connection) -> str:
    tt = template.target_table
    return tt(connection) if callable(tt) else tt


def _materialize_pipeline(
    template: PipelineTemplate,
    connection,
    scope: OwnerScope,
    connection_fingerprint: Optional[str],
    db: Session,
) -> Optional[Pipeline]:
    config = _resolve_extraction_config(template, connection)
    target_table = _resolve_target_table(template, connection)
    fp = compute_pipeline_fingerprint(connection_fingerprint, config)

    template_unique_key = list(template.unique_key) if template.unique_key else None

    def _backfill_unique_key(row: Pipeline) -> None:
        # Backfill unique_key on existing pipelines that pre-date the field.
        # Safe: only writes when the row currently has none and the template
        # declares one. Keeps callers (plugin startup) self-healing.
        if template_unique_key and not row.unique_key:
            row.unique_key = template_unique_key
            db.flush()

    # Primary dedup: same fingerprint already on this scope.
    existing = db.query(Pipeline).filter_by(
        owner_scope_kind=scope.kind,
        owner_scope_id=scope.id,
        pipeline_fingerprint=fp,
    ).first()
    if existing is not None:
        _backfill_unique_key(existing)
        return None

    # Secondary dedup: same (connection, target_table) already exists. Catches
    # rows created by legacy registration code with a different fingerprint
    # format — we don't want a duplicate Pipeline writing to the same table.
    existing = db.query(Pipeline).filter_by(
        owner_scope_kind=scope.kind,
        owner_scope_id=scope.id,
        source_connection_id=connection.id,
        target_table=target_table,
    ).first()
    if existing is not None:
        _backfill_unique_key(existing)
        return None

    row = Pipeline(
        id=str(_uuid.uuid4()),
        owner_scope_kind=scope.kind,
        owner_scope_id=scope.id,
        source_connection_id=connection.id,
        target_table=target_table,
        name=template.name,
        cron=template.cron,
        mode=template.mode,
        incremental_key=template.incremental_key,
        unique_key=list(template.unique_key) if template.unique_key else None,
        extraction_config=config,
        pipeline_fingerprint=fp,
        enabled=template.enabled,
        created_by_user_id=connection.user_id,
    )
    if _try_insert(db, row):
        return row
    return None


def _materialize_transform(
    template: TransformTemplate,
    connection,
    scope: OwnerScope,
    db: Session,
) -> Optional[DbtModel]:
    existing = db.query(DbtModel).filter_by(
        owner_scope_kind=scope.kind,
        owner_scope_id=scope.id,
        name=template.name,
    ).first()
    if existing is not None:
        return None

    row = DbtModel(
        id=str(_uuid.uuid4()),
        owner_scope_kind=scope.kind,
        owner_scope_id=scope.id,
        name=template.name,
        sql=template.sql,
        materialization=template.materialization,
        unique_key=template.unique_key,
        cron=template.cron,
        enabled=template.enabled,
        created_by_user_id=connection.user_id,
    )
    if _try_insert(db, row):
        return row
    return None


def materialize_templates_for_connection(
    connection,
    registration: ConnectorRegistration,
    db: Session,
    *,
    owner_scope: Optional[OwnerScope] = None,
) -> tuple[list[Pipeline], list[DbtModel]]:
    """Create Pipeline + DbtModel rows for any templates the registration ships.

    Returns the rows that were newly created (skipped duplicates are not in the result).
    Caller is responsible for committing the session.
    """
    scope = owner_scope or OwnerScope.from_connection(connection)
    connection_fp = registration.fingerprint(connection) if registration.fingerprint else None

    new_pipelines: list[Pipeline] = []
    for tmpl in registration.pipeline_templates or []:
        try:
            row = _materialize_pipeline(tmpl, connection, scope, connection_fp, db)
            if row is not None:
                new_pipelines.append(row)
        except Exception:
            logger.exception(
                "Failed to materialize pipeline template '%s' for connection %s",
                tmpl.name, connection.id,
            )

    new_transforms: list[DbtModel] = []
    for tmpl in registration.transform_templates or []:
        try:
            row = _materialize_transform(tmpl, connection, scope, db)
            if row is not None:
                new_transforms.append(row)
        except Exception:
            logger.exception(
                "Failed to materialize transform template '%s' for connection %s",
                tmpl.name, connection.id,
            )

    if new_pipelines or new_transforms:
        logger.info(
            "Materialized %d pipeline(s) + %d transform(s) for connection %s (%s)",
            len(new_pipelines), len(new_transforms), connection.id, registration.type_id,
        )
    return new_pipelines, new_transforms
