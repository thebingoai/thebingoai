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
    """Delete a pipeline and its DataPlane target table.

    Steps:
    1. Load pipeline row — raise 404 if not found.
    2. Drop DataPlane target table for the pipeline's scope.
    3. Delete pipeline row (cascade deletes pipeline_runs + dlt_pipeline_states).
    4. Publish lineage:invalidate.
    """
    import json
    from backend.models.pipeline import Pipeline
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane

    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline is None:
        raise LookupError(f"Pipeline {pipeline_id!r} not found")

    scope = OwnerScope(pipeline.owner_scope_kind, pipeline.owner_scope_id)
    plane = get_default_plane(scope, db)

    # Drop DataPlane table — best effort (may not exist yet)
    try:
        if plane.table_exists(scope, pipeline.target_table):
            plane.drop_table(scope, pipeline.target_table)
            logger.info("delete_pipeline: dropped DataPlane table %s for pipeline %s",
                        pipeline.target_table, pipeline_id)
    except Exception as exc:
        logger.warning("delete_pipeline: failed to drop DataPlane table for pipeline %s: %s", pipeline_id, exc)

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
