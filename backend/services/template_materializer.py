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

Dynamic SQL templates: postgres / mysql / sqlite registrations declare no
static `pipeline_templates`. For these the materializer introspects the live
connector via `get_tables()` and synthesises one template per source table at
materialisation time. This keeps `ConnectorRegistration` static while
supporting per-table fan-out for arbitrary SQL sources.
"""
from __future__ import annotations

import logging
import re
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


def _is_dynamic_sql_registration(reg: ConnectorRegistration, *, force: bool = False) -> bool:
    """True iff a registration should fan out one PipelineTemplate per source table.

    A registration qualifies when it ships no static `pipeline_templates`, uses
    the shared `SqlExtractionConfig`, and exposes a `dlt_source_for`. The
    `force=True` override skips the `dlt_source_for` check — used by the SQLite
    post-migration path, which has no dlt source but still needs per-table
    Pipeline rows for dbt sources.yml + lineage references.
    """
    if reg.pipeline_templates:
        return False
    try:
        from backend.connectors.sql_dlt import SqlExtractionConfig
    except Exception:
        return False
    if reg.extraction_config_model is not SqlExtractionConfig:
        return False
    if not force and reg.dlt_source_for is None:
        return False
    return True


_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def _slugify_connection_name(connection, db: Session) -> str:
    """Build a per-connection table prefix.

    Strategy: lowercase + non-alnum-to-underscore. Empty / colliding slugs fall
    back to a deterministic `_{connection.id[:8]}` suffix. Collision is detected
    by checking whether any existing `Pipeline` row in the same scope has a
    target_table starting with the candidate prefix but belongs to a different
    connection.
    """
    raw = (connection.name or "").lower()
    slug = _SLUG_RE.sub("_", raw).strip("_")
    if not slug:
        return f"conn_{str(connection.id)[:8]}"

    scope_kind = getattr(connection, "owner_scope_kind", None) or "user"
    scope_id = getattr(connection, "owner_scope_id", None) or getattr(connection, "user_id", None)
    candidate = slug
    try:
        existing = (
            db.query(Pipeline)
            .filter(
                Pipeline.owner_scope_kind == scope_kind,
                Pipeline.owner_scope_id == scope_id,
                Pipeline.target_table.like(f"{candidate}\\_\\_%"),
            )
            .first()
        )
    except Exception:
        existing = None
    if existing is not None and existing.source_connection_id != connection.id:
        return f"{slug}_{str(connection.id)[:8]}"
    return candidate


_DATE_LIKE_COL_NAMES = (
    "updated_at", "modified_at", "created_at",
    "event_date", "dt", "ts", "timestamp",
)
_DATE_LIKE_TYPE_TOKENS = ("date", "time", "timestamp")


def _detect_incremental_key_for_table(
    reg: ConnectorRegistration,
    connector,
    table: str,
    columns: list[dict],
) -> Optional[str]:
    """Return the best incremental-key column for *table* or None.

    1. Try the connector-specific partition-key helper (postgres / mysql).
    2. Fall back to a date/timestamp heuristic across the known column list.
    """
    type_id = (reg.type_id or "").lower()
    if type_id == "postgres":
        try:
            from backend.connectors.postgres import detect_partition_key as _pg
            pk = _pg(connector, "public", table)
            if pk:
                return pk
        except Exception:
            logger.debug("postgres.detect_partition_key failed for %s", table, exc_info=True)
    elif type_id == "mysql":
        try:
            from backend.connectors.mysql import detect_partition_key as _my
            pk = _my(connector, "", table)
            if pk:
                return pk
        except Exception:
            logger.debug("mysql.detect_partition_key failed for %s", table, exc_info=True)

    # Heuristic: pick the first column whose name is in the date-like set AND
    # whose type contains a date/time token. Preserves source column order.
    name_set = set(_DATE_LIKE_COL_NAMES)
    for col in columns:
        name = (col.get("name") or "").lower()
        ctype = (col.get("type") or "").lower()
        if name in name_set and any(tok in ctype for tok in _DATE_LIKE_TYPE_TOKENS):
            return col["name"]
    return None


def _build_sql_pipeline_templates(
    connection,
    reg: ConnectorRegistration,
    db: Session,
    *,
    force: bool = False,
) -> list[PipelineTemplate]:
    """Introspect a live SQL connector, return one PipelineTemplate per table.

    Populates:
      * `unique_key` from the table's PRIMARY KEY columns (drives BigQueryGCSPlane
        dedup — `_merge_into_native` under the `native_merge_data_plane` flag,
        else `_register_bronze_and_view`).
      * `incremental_key` from source-side partition keys (postgres
        `pg_partitioned_table`, mysql `INFORMATION_SCHEMA.PARTITIONS`) or a
        fallback date-column heuristic.
      * `mode` = `'incremental'` when an `incremental_key` was found, else
        `'full'` (dlt write_disposition flips between merge / replace
        accordingly inside `runner.run_pipeline`).

    On any error (connector unreachable, no tables, schema query failed) we log
    a WARNING and return `[]` so the create-connection flow never breaks.

    `force=True` is used by the SQLite post-migration path, which calls this
    helper against a `SqliteFileConnector` that has no `dlt_source_for`.
    """
    if not _is_dynamic_sql_registration(reg, force=force):
        return []

    try:
        from backend.connectors.factory import get_connector_for_connection
    except Exception:
        logger.warning("get_connector_for_connection unavailable; skipping dynamic SQL templates", exc_info=True)
        return []

    try:
        connector = get_connector_for_connection(connection)
    except Exception:
        logger.warning(
            "Cannot open connector for dynamic SQL templates (connection=%s, type=%s)",
            connection.id, reg.type_id, exc_info=True,
        )
        return []

    try:
        try:
            tables = connector.get_tables(schema=None)
        except Exception:
            logger.warning(
                "get_tables failed for connection %s (%s); skipping dynamic templates",
                connection.id, reg.type_id, exc_info=True,
            )
            return []

        if not tables:
            return []

        prefix = _slugify_connection_name(connection, db)
        conn_name = getattr(connection, "name", None) or f"conn_{str(connection.id)[:8]}"

        templates: list[PipelineTemplate] = []
        for table in tables:
            unique_key: Optional[tuple[str, ...]] = None
            incremental_key: Optional[str] = None
            columns: list[dict] = []
            try:
                schema_obj = connector.get_table_schema(table, schema=None)
                columns = list(getattr(schema_obj, "columns", []) or [])
            except Exception:
                logger.debug(
                    "get_table_schema failed for %s on connection %s; skipping unique_key/incremental_key",
                    table, connection.id, exc_info=True,
                )
                columns = []

            pk_cols = tuple(c["name"] for c in columns if c.get("primary_key"))
            if pk_cols:
                unique_key = pk_cols

            if columns:
                try:
                    incremental_key = _detect_incremental_key_for_table(
                        reg, connector, table, columns,
                    )
                except Exception:
                    logger.debug(
                        "incremental-key detection failed for %s; defaulting to full mode",
                        table, exc_info=True,
                    )
                    incremental_key = None

            mode = "incremental" if incremental_key else "full"

            templates.append(PipelineTemplate(
                name=f"{conn_name}: {table}",
                target_table=f"{prefix}__{table}",
                extraction_config={"tables": [table]},
                cron=None,
                mode=mode,
                incremental_key=incremental_key,
                unique_key=unique_key,
            ))
    finally:
        close_fn = getattr(connector, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                logger.debug("connector.close raised; ignoring", exc_info=True)

    return templates


def _build_sql_transform_templates(
    pipeline_templates: list[PipelineTemplate],
) -> list[TransformTemplate]:
    """Generate a passthrough `stg_<target_table>` dbt model per pipeline template.

    Each model is materialised as a view referencing the matching Pipeline output
    via `{{ source('pipelines', '<target_table>') }}`. The `'pipelines'` source
    name must match what `project_synth._write_sources_yml` emits.
    """
    transforms: list[TransformTemplate] = []
    for tmpl in pipeline_templates:
        target = tmpl.target_table
        if callable(target):
            # Dynamic SQL templates always pass a string; defensive guard so a
            # caller passing a callable for static templates doesn't blow up.
            continue
        transforms.append(TransformTemplate(
            name=f"stg_{target}",
            sql=f"SELECT * FROM {{{{ source('pipelines', '{target}') }}}}",
            materialization="view",
        ))
    return transforms


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

    dynamic_templates: list[PipelineTemplate] = []
    if _is_dynamic_sql_registration(registration):
        dynamic_templates = _build_sql_pipeline_templates(connection, registration, db)

    pipeline_templates = dynamic_templates or list(registration.pipeline_templates or [])

    new_pipelines: list[Pipeline] = []
    for tmpl in pipeline_templates:
        try:
            row = _materialize_pipeline(tmpl, connection, scope, connection_fp, db)
            if row is not None:
                new_pipelines.append(row)
        except Exception:
            logger.exception(
                "Failed to materialize pipeline template '%s' for connection %s",
                tmpl.name, connection.id,
            )

    # Dynamic SQL transforms = one stg_<table> view per dynamic pipeline.
    dynamic_transforms: list[TransformTemplate] = (
        _build_sql_transform_templates(dynamic_templates) if dynamic_templates else []
    )
    transform_templates = dynamic_transforms or list(registration.transform_templates or [])

    new_transforms: list[DbtModel] = []
    for tmpl in transform_templates:
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


def backfill_templates_for_registrations(
    regs: list[ConnectorRegistration],
    db: Session,
) -> dict[str, int]:
    """Backfill templates against existing connections for the given registrations.

    Returns a mapping of `type_id` → number of connections that gained at least
    one new Pipeline or DbtModel row. Caller owns commit lifecycle; this helper
    commits per registration once at least one connection produced new rows so a
    poisoned transaction from a single connection doesn't drag the whole batch.
    """
    from backend.models.database_connection import DatabaseConnection

    filtered = [
        reg for reg in regs
        if reg.pipeline_templates or reg.transform_templates or _is_dynamic_sql_registration(reg)
    ]
    if not filtered:
        return {}

    result: dict[str, int] = {}
    for reg in filtered:
        connections = db.query(DatabaseConnection).filter(
            DatabaseConnection.db_type == reg.type_id,
        ).all()
        result[reg.type_id] = 0
        if not connections:
            continue
        for conn in connections:
            try:
                new_p, new_t = materialize_templates_for_connection(conn, reg, db)
                if new_p or new_t:
                    result[reg.type_id] += 1
            except Exception:
                logger.exception(
                    "Template backfill failed for connection %s (%s)",
                    conn.id, reg.type_id,
                )
                db.rollback()
        if result[reg.type_id]:
            db.commit()
            logger.info(
                "Backfilled templates for %d %s connection(s)",
                result[reg.type_id], reg.type_id,
            )
    return result


def materialize_post_migration(connection, db: Session) -> tuple[list[Pipeline], list[DbtModel]]:
    """Materialise dynamic Pipeline + stg_ DbtModel rows for a migrated SQLite
    connection.

    Called by `backend.migration.substrate._do_migrate` immediately after the
    .sqlite blob's tables land in the DataPlane. Unlike the dynamic SQL path
    used by postgres / mysql at create_connection time, the SQLite registration
    has no `dlt_source_for` — the `force=True` flag on
    `_build_sql_pipeline_templates` skips that check so per-table fan-out still
    runs.

    The resulting Pipeline rows carry `cron=None` (one-shot upload — no
    recurring extraction) but still appear in dbt sources.yml + lineage. The
    stg_ DbtModel rows mirror the per-table passthrough views generated for
    other SQL sources.
    """
    import importlib
    _factory = importlib.import_module("backend.connectors.factory")
    reg = _factory._CONNECTORS.get("sqlite")
    if reg is None:
        logger.warning("No SQLite registration found; skipping post-migration materialise")
        return [], []

    scope = OwnerScope.from_connection(connection)
    connection_fp = reg.fingerprint(connection) if reg.fingerprint else None

    pipeline_templates = _build_sql_pipeline_templates(connection, reg, db, force=True)
    if not pipeline_templates:
        return [], []

    new_pipelines: list[Pipeline] = []
    for tmpl in pipeline_templates:
        try:
            row = _materialize_pipeline(tmpl, connection, scope, connection_fp, db)
            if row is not None:
                new_pipelines.append(row)
        except Exception:
            logger.exception(
                "Post-migration pipeline materialise failed for connection %s table %s",
                connection.id, tmpl.target_table,
            )

    transform_templates = _build_sql_transform_templates(pipeline_templates)
    new_transforms: list[DbtModel] = []
    for tmpl in transform_templates:
        try:
            row = _materialize_transform(tmpl, connection, scope, db)
            if row is not None:
                new_transforms.append(row)
        except Exception:
            logger.exception(
                "Post-migration transform materialise failed for connection %s model %s",
                connection.id, tmpl.name,
            )

    if new_pipelines or new_transforms:
        logger.info(
            "Post-migration materialise: %d pipeline(s) + %d transform(s) for connection %s",
            len(new_pipelines), len(new_transforms), connection.id,
        )
    return new_pipelines, new_transforms


def backfill_templates_for_core_connectors(db: Session) -> dict[str, int]:
    """Backfill dynamic SQL templates for core-registered connectors (postgres /
    mysql / sqlite) that are not loaded via a `BingoPlugin`. Called from
    `backend.main` startup behind `settings.template_backfill_on_startup`.
    """
    import importlib
    from backend.config import settings
    if not settings.template_backfill_on_startup:
        return {}
    _factory = importlib.import_module("backend.connectors.factory")
    return backfill_templates_for_registrations(
        [reg for reg in _factory._CONNECTORS.values() if _is_dynamic_sql_registration(reg)],
        db,
    )
