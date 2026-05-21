"""Connection migration substrate — Phase 3 Task C2.

Migrates a DatabaseConnection's legacy SQLite-on-DO-Spaces blob into the
DataPlane (Parquet) and rewrites widget SQL references as needed.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from backend.database.base import Base, TimestampMixin


# ---------------------------------------------------------------------------
# SQLAlchemy models (defined here, migrated via alembic in Task C3)
# ---------------------------------------------------------------------------

class MigrationJournal(Base, TimestampMixin):
    __tablename__ = "migration_journal"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    legacy_blob_path = Column(Text, nullable=True)
    new_dataplane_table = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    widget_rewrites_applied = Column(JSONB, nullable=False, server_default="[]", default=list)
    pre_migration_dataset_table_name = Column(Text, nullable=True)


class WidgetPendingManualRewrite(Base):
    __tablename__ = "widgets_pending_manual_rewrite"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    widget_id = Column(String(36), nullable=False)
    connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    current_sql = Column(Text, nullable=False)
    suggested_old_table = Column(String(255), nullable=True)
    suggested_new_table = Column(String(255), nullable=True)
    status = Column(String(16), nullable=False, default="pending")
    # 'migration' (Phase 3 substrate rewrite) | 'parse_failure' (Phase 6 lineage)
    source = Column(String(16), nullable=False, default="migration")
    resolved_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------

@dataclass
class WidgetRewriteRecord:
    widget_id: str
    old_sql: str
    new_sql: str


@dataclass
class MigrationResult:
    connection_id: int
    status: str  # "migrated" | "dry_run" | "widget_review_pending" | "skipped" | "failed"
    legacy_blob_path: Optional[str] = None
    new_dataplane_table: Optional[str] = None
    tables_migrated: int = 0
    rows_migrated: int = 0
    widget_rewrites: list[WidgetRewriteRecord] = field(default_factory=list)
    widgets_queued_for_review: int = 0
    error_message: Optional[str] = None


@dataclass
class RollbackResult:
    connection_id: int
    status: str  # "rolled_back" | "no_op" | "failed"
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def migrate_connection(connection_id: int, *, dry_run: bool = False, db=None) -> MigrationResult:
    """Migrate a DatabaseConnection's SQLite blob into the DataPlane.

    If dry_run=True the DataPlane writes and DB mutations are skipped but the
    function still validates the blob and performs a trial widget SQL rewrite.
    """
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return migrate_connection(connection_id, dry_run=dry_run, db=_db)

    from backend.models.database_connection import DatabaseConnection

    connection = db.query(DatabaseConnection).filter(DatabaseConnection.id == connection_id).first()
    if connection is None:
        return MigrationResult(
            connection_id=connection_id,
            status="failed",
            error_message="Connection not found",
        )

    # Check / upsert journal
    journal = db.query(MigrationJournal).filter(MigrationJournal.connection_id == connection_id).first()

    if journal is not None:
        if journal.status == "migrated":
            return MigrationResult(
                connection_id=connection_id,
                status="skipped",
                legacy_blob_path=journal.legacy_blob_path,
                new_dataplane_table=journal.new_dataplane_table,
            )
        if journal.status == "widget_review_pending":
            return MigrationResult(
                connection_id=connection_id,
                status="widget_review_pending",
            )
        # Reset existing non-terminal journal row
        journal.status = "pending"
        journal.started_at = datetime.utcnow()
        journal.error_message = None
    else:
        journal = MigrationJournal(
            connection_id=connection_id,
            status="pending",
            started_at=datetime.utcnow(),
            pre_migration_dataset_table_name=connection.dataset_table_name,
        )
        db.add(journal)
        db.flush()

    # Nothing to migrate
    if connection.dataset_table_name is None:
        db.delete(journal)
        db.commit()
        return MigrationResult(connection_id=connection_id, status="skipped")

    legacy_blob_path = connection.dataset_table_name

    try:
        _result = _do_migrate(connection, journal, dry_run=dry_run, db=db)
    except Exception as exc:  # noqa: BLE001
        journal.status = "failed"
        journal.error_message = str(exc)
        journal.finished_at = datetime.utcnow()
        db.commit()
        return MigrationResult(
            connection_id=connection_id,
            status="failed",
            legacy_blob_path=legacy_blob_path,
            error_message=str(exc),
        )

    return _result


def rollback_connection(connection_id: int, *, db=None) -> RollbackResult:
    """Reverse a completed migration: restore widget SQL and dataset_table_name."""
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return rollback_connection(connection_id, db=_db)

    journal = db.query(MigrationJournal).filter(MigrationJournal.connection_id == connection_id).first()

    if journal is None or journal.status != "migrated":
        return RollbackResult(connection_id=connection_id, status="no_op")

    try:
        from backend.models.database_connection import DatabaseConnection
        from backend.models.dashboard import Dashboard

        connection = db.query(DatabaseConnection).filter(DatabaseConnection.id == connection_id).first()

        # Restore widget SQL from the rewrite log
        rewrites: list[dict] = journal.widget_rewrites_applied or []
        if rewrites:
            # Build a map of widget_id → old_sql for O(1) lookup
            old_sql_by_widget: dict[str, str] = {r["widget_id"]: r["old_sql"] for r in rewrites}

            # Find dashboards that own these widgets
            dashboards = (
                db.query(Dashboard)
                .filter(Dashboard.user_id == connection.user_id if connection else True)
                .all()
            ) if connection else []

            for dashboard in dashboards:
                widgets = dashboard.widgets or []
                changed = False
                for widget in widgets:
                    wid = widget.get("id") or widget.get("widgetId")
                    if wid and wid in old_sql_by_widget:
                        ds = widget.get("dataSource")
                        if ds:
                            ds["sql"] = old_sql_by_widget[wid]
                            changed = True
                if changed:
                    dashboard.widgets = widgets
                    db.add(dashboard)

        # Restore dataset_table_name
        if connection is not None:
            connection.dataset_table_name = journal.pre_migration_dataset_table_name
            db.add(connection)

        journal.status = "rolled_back"
        db.commit()
        return RollbackResult(connection_id=connection_id, status="rolled_back")

    except Exception as exc:  # noqa: BLE001
        return RollbackResult(connection_id=connection_id, status="failed", error_message=str(exc))


def widgets_referencing(connection_id: int, *, db=None) -> list[dict]:
    """Return [{widget_id, dashboard_id, sql}] for all widgets tied to connection_id."""
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return widgets_referencing(connection_id, db=_db)

    from backend.models.dashboard import Dashboard

    results: list[dict] = []
    dashboards = db.query(Dashboard).all()
    for dashboard in dashboards:
        for widget in dashboard.widgets or []:
            ds = widget.get("dataSource") or {}
            if ds.get("connectionId") == connection_id:
                sql = ds.get("sql", "")
                wid = widget.get("id") or widget.get("widgetId", "")
                results.append({"widget_id": wid, "dashboard_id": dashboard.id, "sql": sql})
    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _do_migrate(connection, journal: MigrationJournal, *, dry_run: bool, db) -> MigrationResult:
    """Core migration logic — called inside migrate_connection after guards."""
    import io
    import sqlite3
    import tempfile

    import pyarrow as pa

    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane
    import backend.services.object_storage as object_storage

    scope = OwnerScope.from_connection(connection)
    plane = get_default_plane(scope, db)

    legacy_blob_path: str = connection.dataset_table_name  # type: ignore[assignment]

    # Download SQLite blob
    blob_data = object_storage.download_bytes(legacy_blob_path)
    if blob_data is None:
        raise ValueError(f"Legacy blob not found in object storage: {legacy_blob_path!r}")

    # Write to temp file and open read-only
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp.write(blob_data)
        tmp_path = tmp.name

    tables_migrated = 0
    rows_migrated = 0
    legacy_table_names: list[str] = []
    new_dataplane_table: Optional[str] = None

    try:
        conn_ro = sqlite3.connect(f"file:{tmp_path}?mode=ro", uri=True)
        try:
            cur = conn_ro.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%' AND name != '_meta'"
            )
            table_rows = cur.fetchall()

            for (table_name,) in table_rows:
                legacy_table_names.append(table_name)

                # Capture PRIMARY KEY columns so the DataPlane can register a
                # dedup view (bronze+silver pattern) or MERGE-into-native table
                # under the `native_merge_data_plane` flag.
                pk_cols: tuple[str, ...] = ()
                try:
                    pk_cursor = conn_ro.execute(f'PRAGMA table_info("{table_name}")')
                    pk_cols = tuple(
                        row[1] for row in pk_cursor.fetchall() if row[5]
                    )
                except Exception:
                    pk_cols = ()

                cur.execute(f"SELECT * FROM \"{table_name}\"")
                col_names = [desc[0] for desc in cur.description]
                data_rows = cur.fetchall()
                rows_migrated += len(data_rows)

                if not dry_run:
                    # Build PyArrow table and write to DataPlane
                    col_data: dict[str, list] = {c: [] for c in col_names}
                    for row in data_rows:
                        for c, v in zip(col_names, row):
                            col_data[c].append(v)

                    arrow_arrays = [pa.array(col_data[c]) for c in col_names]
                    arrow_table = pa.table(dict(zip(col_names, arrow_arrays)))

                    write_kwargs: dict = {"mode": "overwrite"}
                    if pk_cols:
                        write_kwargs["unique_key"] = pk_cols
                    plane.write_parquet(scope, table_name, arrow_table, **write_kwargs)
                    new_dataplane_table = table_name  # last table; spec uses singular

                tables_migrated += 1
        finally:
            conn_ro.close()
    finally:
        import os
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Widget SQL rewrite
    widget_rewrites, queued_count = _rewrite_widgets_for_connection(
        connection, legacy_table_names, new_dataplane_prefix="", dry_run=dry_run, db=db
    )

    if queued_count > 0:
        journal.status = "widget_review_pending"
        db.flush()
        return MigrationResult(
            connection_id=connection.id,
            status="widget_review_pending",
            legacy_blob_path=legacy_blob_path,
            tables_migrated=tables_migrated,
            rows_migrated=rows_migrated,
            widget_rewrites=widget_rewrites,
            widgets_queued_for_review=queued_count,
        )

    if not dry_run:
        # Clear the FK reference before deleting the blob
        connection.dataset_table_name = None
        db.add(connection)

        # Soft-delete legacy blob
        object_storage.delete_object(legacy_blob_path)

        # Serialise widget rewrites for the journal
        journal.widget_rewrites_applied = [
            {"widget_id": r.widget_id, "old_sql": r.old_sql, "new_sql": r.new_sql}
            for r in widget_rewrites
        ]
        journal.legacy_blob_path = legacy_blob_path
        journal.new_dataplane_table = new_dataplane_table
        journal.status = "migrated"
        journal.finished_at = datetime.utcnow()

        # Auto-materialise Pipeline + stg_ DbtModel rows for every migrated
        # table so the dbt project's sources.yml + staging layer references the
        # new DataPlane data. Failures are non-fatal — the post-migration sync
        # can be re-run idempotently. cron=None so the dispatcher never picks
        # the rows up (SQLite is a one-shot upload).
        try:
            from backend.services.template_materializer import materialize_post_migration
            materialize_post_migration(connection, db)
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "materialize_post_migration failed for connection %s; "
                "Pipeline + stg_ rows will be missing until re-run",
                connection.id, exc_info=True,
            )

        db.commit()

    final_status = "dry_run" if dry_run else "migrated"
    return MigrationResult(
        connection_id=connection.id,
        status=final_status,
        legacy_blob_path=legacy_blob_path,
        new_dataplane_table=new_dataplane_table,
        tables_migrated=tables_migrated,
        rows_migrated=rows_migrated,
        widget_rewrites=widget_rewrites,
        widgets_queued_for_review=0,
    )


def _rewrite_widgets_for_connection(
    connection,
    legacy_table_names: list[str],
    new_dataplane_prefix: str,
    dry_run: bool,
    db,
) -> tuple[list[WidgetRewriteRecord], int]:
    """Rewrite widget SQL for all dashboards owned by connection.user_id.

    Returns (rewrites_applied, widgets_queued_count).
    """
    from backend.models.dashboard import Dashboard
    from backend.utils.sql_refs import rewrite_table_refs

    # DataPlane uses the same table names — mapping is identity unless a prefix is given.
    if new_dataplane_prefix:
        mapping: dict[str, str] = {t: f"{new_dataplane_prefix}_{t}" for t in legacy_table_names}
    else:
        mapping = {t: t for t in legacy_table_names}

    dashboards = (
        db.query(Dashboard)
        .filter(Dashboard.user_id == connection.user_id)
        .all()
    )

    rewrites_applied: list[WidgetRewriteRecord] = []
    queued_count = 0

    for dashboard in dashboards:
        widgets = dashboard.widgets or []
        dashboard_changed = False

        for widget in widgets:
            ds = widget.get("dataSource") or {}
            if ds.get("connectionId") != connection.id:
                continue

            sql = ds.get("sql") or ""
            if not sql:
                continue

            wid = widget.get("id") or widget.get("widgetId") or ""
            new_sql, success = rewrite_table_refs(sql, mapping)

            if not success:
                # Queue for manual review
                pending = WidgetPendingManualRewrite(
                    widget_id=wid,
                    connection_id=connection.id,
                    current_sql=sql,
                    suggested_old_table=legacy_table_names[0] if legacy_table_names else None,
                    suggested_new_table=(
                        mapping[legacy_table_names[0]] if legacy_table_names else None
                    ),
                )
                db.add(pending)
                queued_count += 1
                continue

            if new_sql != sql:
                record = WidgetRewriteRecord(widget_id=wid, old_sql=sql, new_sql=new_sql)
                rewrites_applied.append(record)

                if not dry_run:
                    ds["sql"] = new_sql
                    dashboard_changed = True

        if dashboard_changed:
            dashboard.widgets = widgets
            db.add(dashboard)

    if queued_count > 0:
        db.flush()

    return rewrites_applied, queued_count
