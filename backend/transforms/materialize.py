"""GAP-3: land dbt-transform outputs in the DataPlane Parquet lake.

dbt computes a model natively (DuckDB file dev / BQ dataset prod); this reads
the materialized result back into Arrow (`plane.read_dbt_model`, env-specific)
and writes it via `plane.write_parquet` — the same call pipelines use. dbt
outputs then become structurally identical to pipeline `target_table`: same
Parquet layout, same DuckDB serving, same dt= incremental.

`view` materializations store no data and are skipped (dashboard-backing models
must be `table`/`incremental`).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def materialize_dbt_model_to_dataplane(scope, model_name: str, *, db=None) -> bool:
    """Copy one dbt-materialized model into the DataPlane Parquet lake.

    Returns True if written, False if skipped (view / model row missing).
    Reuses `write_parquet(mode, unique_key)`: incremental models append with
    their unique key (driving the plane's merge/dedup), tables overwrite.
    """
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return materialize_dbt_model_to_dataplane(scope, model_name, db=_db)

    from backend.models.transforms import DbtModel
    from backend.services.data_plane_service import get_default_plane

    model = (
        db.query(DbtModel)
        .filter(
            DbtModel.owner_scope_kind == scope.kind,
            DbtModel.owner_scope_id == scope.id,
            DbtModel.name == model_name,
        )
        .first()
    )
    if model is not None and model.materialization == "view":
        logger.debug("materialize_dbt_model_to_dataplane: skipping view model %s", model_name)
        return False

    plane = get_default_plane(scope, db)
    arrow = plane.read_dbt_model(scope, model_name)

    mode = "overwrite"
    unique_key = None
    if model is not None and model.materialization == "incremental" and model.unique_key:
        mode = "append"
        unique_key = tuple(k.strip() for k in model.unique_key.split(",") if k.strip())

    plane.write_parquet(scope, model_name, arrow, mode=mode, unique_key=unique_key)
    logger.info(
        "Materialized dbt model %s → DataPlane (%s, %d rows)",
        model_name, mode, arrow.num_rows,
    )
    return True
