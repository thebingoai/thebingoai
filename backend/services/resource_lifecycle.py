"""Resource lifecycle cascade handlers (Phase 2).

Central place for delete cascades that span multiple tables / services.
Phase 2 contributes: delete_pipeline + connection_delete_guard.
Phase 4 will add: delete_dbt_model.
Phase G will wrap each handler with audit-log emission.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def delete_pipeline(pipeline_id: str, db) -> None:
    """Delete a pipeline row + its run history. DataPlane data is preserved.

    Steps:
    1. Load pipeline row — raise 404 if not found.
    2. Delete pipeline row (cascade deletes pipeline_runs + dlt_pipeline_states).
    3. Publish lineage:invalidate.

    Bingo's no-delete policy: the target table on the DataPlane (BQ external
    table + GCS parquet files / Local parquet files) is left in place. Operators
    can drop the table + GCS prefix in their GCP project (or rm the local dir)
    if they want to reclaim storage.
    """
    import json
    from backend.models.pipeline import Pipeline
    from backend.data_plane.scope import OwnerScope

    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline is None:
        raise LookupError(f"Pipeline {pipeline_id!r} not found")

    scope = OwnerScope(pipeline.owner_scope_kind, pipeline.owner_scope_id)
    logger.info(
        "delete_pipeline %s: removing metadata only; DataPlane data for table %r "
        "in scope %s preserved (Bingo no-delete policy).",
        pipeline_id, pipeline.target_table, scope.as_path(),
    )

    db.delete(pipeline)
    db.flush()

    # Publish lineage:invalidate
    try:
        import redis
        from backend.config import settings
        r = redis.from_url(settings.redis_url)
        r.publish("lineage:invalidate", json.dumps({
            "pipeline_id": pipeline_id,
            "scope_kind": scope.kind,
            "scope_id": scope.id,
        }))
        r.close()
    except Exception:
        logger.warning("delete_pipeline: failed to publish lineage:invalidate for pipeline %s", pipeline_id)


def delete_dbt_model(model_id: str, db) -> None:
    """Delete a dbt model row + scope-level dbt_runs. Materialized data preserved.

    Steps:
    1. Load model row — raise 404 if not found.
    2. Manually delete dbt_runs (no FK cascade — runs are scope-level).
    3. Delete model row.
    4. Publish lineage:invalidate.

    Bingo's no-delete policy: the materialized output (BQ table or Local
    parquet) is left in place. Operators clean up GCP-side / filesystem-side
    if they want to reclaim storage.
    """
    import json
    from backend.models.transforms import DbtModel
    from backend.data_plane.scope import OwnerScope

    model = db.query(DbtModel).filter(DbtModel.id == model_id).first()
    if model is None:
        raise LookupError(f"DbtModel {model_id!r} not found")

    scope = OwnerScope(model.owner_scope_kind, model.owner_scope_id)
    logger.info(
        "delete_dbt_model %s: removing metadata only; materialized table %r in scope %s "
        "preserved (Bingo no-delete policy).",
        model_id, model.name, scope.as_path(),
    )

    # Manually delete dbt_runs (no FK cascade — runs are scope-level)
    from backend.models.transforms import DbtRun
    db.query(DbtRun).filter(
        DbtRun.owner_scope_kind == model.owner_scope_kind,
        DbtRun.owner_scope_id == model.owner_scope_id,
    ).delete(synchronize_session=False)

    db.delete(model)
    db.flush()

    # Publish lineage:invalidate
    try:
        import redis
        from backend.config import settings
        r = redis.from_url(settings.redis_url)
        r.publish("lineage:invalidate", json.dumps({
            "model_id": model_id,
            "scope_kind": scope.kind,
            "scope_id": scope.id,
        }))
        r.close()
    except Exception:
        logger.warning("delete_dbt_model: failed to publish lineage:invalidate for model %s", model_id)


def guard_connection_delete(connection_id: int, db, *, cascade: bool = False) -> None:
    """Raise 409 if connection has dependent Pipelines (unless cascade=True).

    Call this from the connection-delete endpoint BEFORE deleting.
    If cascade=True, delete all dependent Pipelines first (via delete_pipeline).
    """
    from backend.models.pipeline import Pipeline

    dependent = db.query(Pipeline).filter(
        Pipeline.source_connection_id == connection_id
    ).all()

    if not dependent:
        return

    if not cascade:
        pipeline_ids = [p.id for p in dependent]
        raise RuntimeError(
            f"Connection {connection_id} has {len(dependent)} dependent pipeline(s): "
            f"{pipeline_ids}. Use cascade=true to delete them."
        )

    for pipeline in dependent:
        delete_pipeline(pipeline.id, db)
    logger.info("guard_connection_delete: cascade-deleted %d pipeline(s) for connection %d",
                len(dependent), connection_id)
