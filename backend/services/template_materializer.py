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
    # Release the SAVEPOINT on success. Without this every inserted row leaves an
    # open nested savepoint; the outer commit then releases them recursively and
    # a large connection (~2000 pipeline+transform rows) overflows Python's
    # recursion limit -> RecursionError. RELEASE keeps nesting flat; the outer
    # transaction still controls the final commit/rollback.
    sp.commit()
    return True


def _resolve_extraction_config(template: PipelineTemplate, connection) -> dict:
    cfg = template.extraction_config
    return cfg(connection) if callable(cfg) else dict(cfg)


def _resolve_target_table(template: PipelineTemplate, connection) -> str:
    tt = template.target_table
    return tt(connection) if callable(tt) else tt


def _spec_from_template(template: PipelineTemplate, connection) -> Optional[dict]:
    """Map a per-table PipelineTemplate to a PipelineSchedule.tables spec dict."""
    src_tables = (_resolve_extraction_config(template, connection).get("tables") or [])
    if not src_tables:
        return None
    return {
        "source_table": src_tables[0],
        "target_table": _resolve_target_table(template, connection),
        "mode": template.mode,
        "incremental_key": template.incremental_key,
        "unique_key": list(template.unique_key) if template.unique_key else None,
        "enabled": True,
    }


def build_specs_for_tables(connection, reg, db: Session, selected: list[str]) -> list[dict]:
    """Re-derive PipelineSchedule.tables specs for `selected` source tables.

    Reuses the same per-table introspection as connection-create materialization
    (`_build_sql_pipeline_templates` → watermark / PK / target naming) so a schedule
    edit produces specs identical to what create would. Returns specs in `selected`
    order; unknown table names are skipped.
    """
    templates = _build_sql_pipeline_templates(connection, reg, db)
    by_source: dict[str, dict] = {}
    for tmpl in templates:
        spec = _spec_from_template(tmpl, connection)
        if spec is not None:
            by_source[spec["source_table"]] = spec
    return [by_source[t] for t in selected if t in by_source]


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
    # Seed `next_run_at` when cron is set — otherwise `dispatch_pipelines`
    # filter (`next_run_at <= now`) silently skips the row because NULL
    # comparisons never match.
    if row.cron and row.enabled:
        try:
            from backend.utils.cron import compute_next_run
            row.next_run_at = compute_next_run(row.cron, row.timezone or "UTC")
        except Exception:
            logger.debug("compute_next_run failed for template %s", template.name, exc_info=True)
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

        # Collect columns up-front so the watermark classifier can run as a
        # single batched call across all tables (cheaper for the LLM-first
        # path; deterministic-only path is also fine with a batched dict).
        columns_by_table: dict[str, list[dict]] = {}
        unique_key_by_table: dict[str, Optional[tuple[str, ...]]] = {}
        for table in tables:
            try:
                schema_obj = connector.get_table_schema(table, schema=None)
                cols = list(getattr(schema_obj, "columns", []) or [])
            except Exception:
                logger.debug(
                    "get_table_schema failed for %s on connection %s; skipping unique_key/incremental_key",
                    table, connection.id, exc_info=True,
                )
                cols = []
            columns_by_table[table] = cols
            pk_cols = tuple(c["name"] for c in cols if c.get("primary_key"))
            unique_key_by_table[table] = pk_cols or None

        try:
            from backend.services.watermark_classifier import resolve_watermark
            watermark_by_table = resolve_watermark(reg, connector, tables, columns_by_table)
        except Exception:
            logger.debug(
                "resolve_watermark raised on connection %s; defaulting to full-snapshot mode",
                connection.id, exc_info=True,
            )
            watermark_by_table = {t: None for t in tables}

        templates: list[PipelineTemplate] = []
        for table in tables:
            incremental_key = watermark_by_table.get(table)
            mode = "incremental" if incremental_key else "full"
            templates.append(PipelineTemplate(
                name=f"{conn_name}: {table}",
                target_table=f"{prefix}__{table}",
                extraction_config={"tables": [table]},
                # Auto-enabled daily ingest at 02:00 UTC (checklist default).
                # Override via PATCH /api/pipelines/{id} once the row exists.
                cron="0 2 * * *",
                mode=mode,
                incremental_key=incremental_key,
                unique_key=unique_key_by_table.get(table),
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


def _detect_snapshot_date_column(columns: list[dict]) -> Optional[str]:
    """Thin shim over the shared watermark classifier's deterministic matcher.

    Kept for callers/tests that import this symbol directly; new code should
    call `backend.services.watermark_classifier.classify_table` (or the batched
    `classify_connection`).
    """
    from backend.services.watermark_classifier import classify_table

    return classify_table(columns)


def _apply_mysql_t1_schedule(new_pipelines: list[Pipeline], connection, db: Session) -> None:
    """Make freshly-created MySQL pipelines self-running daily.

    Per the materialize-to-plane design:
      - **Date-column detected** (live-schema introspection) → `mode='incremental'`
        with a dlt watermark cursor on that column. **No `initial_value`** is
        seeded, so the first run pulls all historical data up to and including
        T-1 (yesterday end). `end_value` is computed at run time in
        `sql_dlt_source` as the start of today UTC (exclusive) — same-day rows
        are never ingested when an incremental cursor is configured.
      - **No date column** → `mode='full'` snapshot each run (loads the whole
        table; no T-1 cap).

    Always sets `cron` + seeds `next_run_at` so the beat dispatcher picks it up.

    Applied at the materialization layer — the per-table `PipelineTemplate` is
    left untouched. No-op for non-MySQL connections.
    """
    if not new_pipelines or (getattr(connection, "db_type", "") or "").lower() != "mysql":
        return

    from datetime import datetime, timedelta, timezone

    from backend.config import settings
    from backend.connectors.factory import get_connector_for_connection
    from backend.utils.cron import compute_next_run

    cron = getattr(settings, "default_sql_pipeline_cron", "0 2 * * *")

    # Lower-bound for first run: T-n, where n = `first_ingest_lookback_days`.
    #   - N > 0  → first run pulls `[today − N days 00:00 UTC, today 00:00 UTC)`
    #             (e.g. N=1 → yesterday only; N=7 → last 7 days).
    #   - N ≤ 0 → no lower bound; first run pulls all history up to T-1.
    # The upper bound (`end_value = today 00:00 UTC`, exclusive) is always
    # applied at run time inside `sql_dlt_source` so same-day rows are never
    # ingested when an incremental cursor is configured.
    lookback_days = int(getattr(settings, "first_ingest_lookback_days", 0) or 0)
    if lookback_days > 0:
        initial_dt = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
    else:
        initial_dt = None

    try:
        connector = get_connector_for_connection(connection)
    except Exception:
        logger.warning(
            "MySQL schedule: cannot open connector for connection %s; skipping",
            connection.id, exc_info=True,
        )
        return

    try:
        # Collect schemas for every single-table pipeline in one pass so the
        # watermark classifier can score them in a single batched LLM call.
        table_schemas: dict[str, list[dict]] = {}
        for p in new_pipelines:
            tables = (p.extraction_config or {}).get("tables") or []
            if len(tables) != 1:
                continue
            try:
                schema_obj = connector.get_table_schema(tables[0], schema=None)
                table_schemas[tables[0]] = list(getattr(schema_obj, "columns", []) or [])
            except Exception:
                logger.debug(
                    "schema fetch failed for %s; pipeline left as full snapshot",
                    tables[0], exc_info=True,
                )

        # Sync path uses the deterministic matcher only — fast (no I/O) and
        # safe under request latency. LLM refinement (when configured) runs in
        # a background Celery task enqueued from `api/connections.py` after
        # commit, so the connect handler returns immediately.
        try:
            from backend.services.watermark_classifier import classify_table
            watermark_map = {t: classify_table(cols) for t, cols in table_schemas.items()}
        except Exception:
            logger.warning(
                "watermark classifier crashed for connection %s; defaulting all tables to full snapshot",
                connection.id, exc_info=True,
            )
            watermark_map = {t: None for t in table_schemas}

        for p in new_pipelines:
            tables = (p.extraction_config or {}).get("tables") or []
            date_col = watermark_map.get(tables[0]) if len(tables) == 1 else None
            new_cfg = dict(p.extraction_config or {})
            if date_col:
                p.mode = "incremental"
                p.incremental_key = date_col
                new_cfg["incremental_key"] = date_col
                if initial_dt is not None:
                    # Seed the first-run lower bound (T-n). dlt persists the
                    # cursor after run 1, so this value is only consulted once.
                    new_cfg["initial_value"] = initial_dt.isoformat()
                else:
                    # Lookback disabled → first run pulls all history up to
                    # T-1 (yesterday end), bounded only by `end_value`.
                    new_cfg.pop("initial_value", None)
            else:
                p.mode = "full"
                # Drop any stale incremental hints — full snapshot loads fully.
                new_cfg.pop("incremental_key", None)
                new_cfg.pop("initial_value", None)
            p.extraction_config = new_cfg
            p.cron = cron
            try:
                p.next_run_at = compute_next_run(cron, getattr(p, "timezone", None) or "UTC")
            except Exception:
                logger.warning(
                    "compute_next_run failed for cron %r; pipeline %s left unscheduled",
                    cron, p.id, exc_info=True,
                )
        db.flush()
    finally:
        close = getattr(connector, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass


def _materialize_sql_pipeline_v2(
    connection,
    scope: OwnerScope,
    connection_fp: Optional[str],
    dynamic_templates: list[PipelineTemplate],
    db: Session,
) -> list[Pipeline]:
    """New model: collapse the per-table detection templates into ONE Pipeline
    (cron null) + ONE default daily schedule whose `tables` JSON carries every
    table's ingest spec. Returns [pipeline] when newly created, else [].

    Idempotent: if a new-model pipeline (cron null) already exists for this
    (scope, connection), leaves it and its schedules untouched — avoids
    clobbering any schedules the user has since customised.
    """
    from backend.models.pipeline import PipelineSchedule
    from backend.utils.cron import compute_next_run

    specs: list[dict] = []
    for tmpl in dynamic_templates:
        spec = _spec_from_template(tmpl, connection)
        if spec is not None:
            specs.append(spec)
    if not specs:
        return []

    # Already has a new-model pipeline (cron null) → idempotent, leave it.
    existing = db.query(Pipeline).filter(
        Pipeline.owner_scope_kind == scope.kind,
        Pipeline.owner_scope_id == scope.id,
        Pipeline.source_connection_id == connection.id,
        Pipeline.cron.is_(None),
    ).first()
    if existing is not None:
        return []

    # Already has LEGACY pipelines (cron set) → don't mix models, or both the
    # legacy cron rows and the new schedule would ingest the same tables.
    # Existing connections are migrated in a separate step.
    legacy = db.query(Pipeline).filter(
        Pipeline.owner_scope_kind == scope.kind,
        Pipeline.owner_scope_id == scope.id,
        Pipeline.source_connection_id == connection.id,
        Pipeline.cron.isnot(None),
    ).first()
    if legacy is not None:
        return []

    pipeline = Pipeline(
        id=str(_uuid.uuid4()),
        owner_scope_kind=scope.kind,
        owner_scope_id=scope.id,
        source_connection_id=connection.id,
        target_table=None,
        name=getattr(connection, "name", None) or f"conn_{connection.id}",
        cron=None,
        mode="full",
        extraction_config={},
        pipeline_fingerprint=compute_pipeline_fingerprint(
            connection_fp, {"connection_id": connection.id},
        ),
        enabled=True,
        created_by_user_id=connection.user_id,
    )
    if not _try_insert(db, pipeline):
        return []  # race: another worker created it

    cron = "0 2 * * *"
    sched = PipelineSchedule(
        id=str(_uuid.uuid4()),
        pipeline_id=pipeline.id,
        name="Daily",
        cron=cron,
        timezone="UTC",
        tables=specs,
        enabled=True,
    )
    try:
        sched.next_run_at = compute_next_run(cron, "UTC")
    except Exception:
        logger.debug("compute_next_run failed for default schedule", exc_info=True)
    _try_insert(db, sched)
    return [pipeline]


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

    new_pipelines: list[Pipeline] = []
    if dynamic_templates:
        # New model: one Pipeline + one default schedule for the whole
        # connection (per-table specs live in the schedule's `tables` JSON).
        new_pipelines = _materialize_sql_pipeline_v2(
            connection, scope, connection_fp, dynamic_templates, db,
        )
    else:
        # Static-template connectors (GA4, etc.) keep per-template pipelines.
        for tmpl in list(registration.pipeline_templates or []):
            try:
                row = _materialize_pipeline(tmpl, connection, scope, connection_fp, db)
                if row is not None:
                    new_pipelines.append(row)
            except Exception:
                logger.exception(
                    "Failed to materialize pipeline template '%s' for connection %s",
                    tmpl.name, connection.id,
                )

        # Commit the new pipeline rows NOW — before _apply_mysql_t1_schedule below
        # queries the *source* DB (connector.get_table_schema). That call can hang on
        # a slow/unreachable source, and we must not hold the
        # uq_pipeline_scope_fingerprint lock (taken via the SAVEPOINT in _try_insert)
        # across it: every pod runs this backfill at startup, so a held lock stalls
        # concurrent pods idle-in-transaction for minutes and exhausts the managed
        # PG's connection cap (the 2026-06-24 outage). The T-1 schedule below only
        # UPDATEs these already-committed rows, so there is no insert-lock race left.
        if new_pipelines:
            try:
                db.commit()
            except Exception:
                logger.warning(
                    "commit of new pipelines failed for connection %s; rolling back",
                    connection.id, exc_info=True,
                )
                db.rollback()

        # MySQL: make the new pipelines self-running daily T-1 snapshots (cron +
        # next_run_at + date-capped full snapshot). No-op for static templates.
        try:
            _apply_mysql_t1_schedule(new_pipelines, connection, db)
        except Exception:
            logger.warning(
                "MySQL T-1 schedule application failed for connection %s", connection.id, exc_info=True
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
    one new Pipeline or DbtModel row. Caller owns the outer commit lifecycle;
    this helper commits **per connection** (see the loop) so the
    `uq_pipeline_scope_fingerprint` lock taken by each insert is released before
    the next connection's (slow) introspection runs.
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
            except Exception:
                logger.exception(
                    "Template backfill failed for connection %s (%s)",
                    conn.id, reg.type_id,
                )
                db.rollback()
                continue
            # Commit (or release) per connection — NOT once per registration.
            # Each insert takes a uq_pipeline_scope_fingerprint lock (via the
            # SAVEPOINT in _try_insert) held until commit. Every pod runs this
            # backfill at startup, so a deploy starting N pods together has them
            # all INSERT the same fingerprints. Deferring the commit to the end
            # of the registration loop holds that lock across the slow
            # get_tables() introspection of *later* connections — turning a
            # millisecond race into minutes of blocked, piled-up transactions
            # that exhaust the DB connection cap. Committing here bounds the lock
            # to one connection's inserts so concurrent pods resolve via
            # IntegrityError instantly instead of stampeding.
            if new_p or new_t:
                db.commit()
                result[reg.type_id] += 1
            else:
                db.rollback()  # nothing new — drop the read txn, don't hold it
        if result[reg.type_id]:
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


_BACKFILL_LEASE_KEY = "bingo:template_backfill:lease"
# ponytail: fixed TTL, no renewal. A backfill that outruns it lets a second
# replica start — same idempotent work, no corruption, just the introspection
# paid twice. Add a renewal heartbeat only if that actually shows up in logs.
_BACKFILL_LEASE_TTL = 900  # seconds


def run_startup_backfill() -> None:
    """Run the whole startup template backfill: every loaded plugin, then the
    core connectors. Entry point for the daemon thread started in
    `backend.main.lifespan`.

    Single-flight across replicas. Pods now reach Ready in seconds, so a rolling
    deploy has every replica in this function at once — before the work was
    deferred, readiness gated on it and serialised it. A Redis lease
    (`SET NX EX`) keeps one process doing the live source-DB introspection.
    Losers skip rather than queue: the work is idempotent and reruns on the next
    boot, and queueing would just recreate the pile-up.

    Redis rather than `pg_try_advisory_lock`, which is what this first shipped
    with and does not hold on this deployment — see `services/redis_lease.py`
    for the measured mechanism.

    Also cheaper: nothing holds a database connection for the duration, which
    matters against the managed PG's 25-connection cap.

    Fails open. If Redis is unreachable the backfill runs unguarded — losing
    single-flight beats losing the backfill.

    Never raises. This runs detached on a thread, so anything escaping would be
    lost — every failure path logs instead.
    """
    try:
        from backend.database.session import SessionLocal
        from backend.plugins.loader import backfill_all_plugin_templates
        from backend.services.redis_lease import acquire_lease, release_lease

        lease = acquire_lease(_BACKFILL_LEASE_KEY, _BACKFILL_LEASE_TTL)
        if lease is None:
            logger.info("Template backfill already running on another replica, skipping")
            return

        try:
            with SessionLocal() as db:
                try:
                    backfill_all_plugin_templates()
                except Exception:
                    logger.warning("Plugin template backfill failed", exc_info=True)
                try:
                    backfill_templates_for_core_connectors(db)
                except Exception:
                    logger.warning("Core-connector template backfill failed", exc_info=True)
        finally:
            release_lease(_BACKFILL_LEASE_KEY, lease)
    except Exception:
        logger.exception("Startup template backfill aborted")
