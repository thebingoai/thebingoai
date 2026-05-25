"""Phase 3 stored-SQL dialect migration: transpile widget SQL BigQuery → DuckDB.

The per-Org cutover flips each dashboard's persisted widget SQL from BigQuery to
DuckDB (once), so the read path runs already-DuckDB SQL with no read-time
transpile. This module holds the core, side-effect-light transformation; the
per-Org orchestration (journal, rollback, trigger) wraps it.

Reuses the Phase 1 `transpile_bq_to_duckdb` utility — which fails loudly on
un-transpilable SQL — so a widget that can't be safely converted is reported
rather than silently rewritten to broken DuckDB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from backend.database.base import Base
from backend.utils.sql_refs import UntranspilableSQLError, transpile_bq_to_duckdb


# Per-dashboard dialect marker + rollback store. A row's presence means the
# dashboard's stored SQL is DuckDB (serving may use the DuckDB path):
#   status='migrated'    — converted from BigQuery; widget_rewrites holds the
#                          original SQL per widget for rollback.
#   status='born_duckdb' — created after the Org's agent flip; already DuckDB,
#                          nothing to roll back.
class DashboardDialectMigration(Base):
    __tablename__ = "dashboard_dialect_migration"

    dashboard_id = Column(Integer, ForeignKey("dashboards.id"), primary_key=True)
    status = Column(String(16), nullable=False)  # 'migrated' | 'born_duckdb'
    widget_rewrites = Column(JSONB, nullable=False, server_default="[]", default=list)
    migrated_at = Column(DateTime, nullable=False, server_default=func.now(), default=datetime.utcnow)


@dataclass
class WidgetSqlRewrite:
    widget_id: str
    old_sql: str
    new_sql: str


@dataclass
class DashboardDialectResult:
    """Outcome of transpiling one dashboard's widgets."""
    rewrites: list[WidgetSqlRewrite] = field(default_factory=list)
    unparseable: list[str] = field(default_factory=list)  # widget_ids that couldn't transpile
    changed: bool = False

    @property
    def ok(self) -> bool:
        """True when every widget transpiled — safe to cut this dashboard over."""
        return not self.unparseable


def transpile_dashboard_widgets(widgets: list[dict], *, dry_run: bool = False) -> DashboardDialectResult:
    """Transpile every widget's `dataSource.sql` BigQuery → DuckDB, in place.

    Only `dataSource.sql` is rewritten — `dataSource.mapping`, `widget.config`,
    and all sibling fields are left untouched. Widgets whose SQL can't be
    transpiled are collected in `unparseable` and left unchanged (the caller
    halts that dashboard's cutover). With `dry_run=True` nothing is mutated;
    the rewrites/unparseable lists are still computed.
    """
    result = DashboardDialectResult()
    for widget in widgets:
        ds = widget.get("dataSource")
        if not isinstance(ds, dict):
            continue
        sql = ds.get("sql")
        if not sql:
            continue
        wid = widget.get("id") or widget.get("widgetId") or ""

        try:
            new_sql = transpile_bq_to_duckdb(sql)
        except UntranspilableSQLError:
            result.unparseable.append(wid)
            continue

        if new_sql != sql:
            result.rewrites.append(WidgetSqlRewrite(widget_id=wid, old_sql=sql, new_sql=new_sql))
            if not dry_run:
                ds["sql"] = new_sql  # mapping + other dataSource fields preserved
                result.changed = True

    return result


# ---------------------------------------------------------------------------
# Per-Org cutover orchestration (journal-gated)
# ---------------------------------------------------------------------------

@dataclass
class DashboardMigrationOutcome:
    dashboard_id: int
    # 'migrated' | 'dry_run' | 'skipped' (already journaled) | 'halted' (un-transpilable)
    status: str
    rewrites: list[WidgetSqlRewrite] = field(default_factory=list)
    unparseable: list[str] = field(default_factory=list)


def is_duckdb_ready(dashboard_id, db) -> bool:
    """True when the dashboard is journaled DuckDB (migrated or born-DuckDB)."""
    if dashboard_id is None:
        return False
    return (
        db.query(DashboardDialectMigration)
        .filter(DashboardDialectMigration.dashboard_id == dashboard_id)
        .first()
        is not None
    )


def mark_born_duckdb(dashboard_id: int, db) -> None:
    """Journal a freshly-created dashboard as born-DuckDB (idempotent).

    Called from the dashboard create path when the Org has the agent flipped, so
    its already-DuckDB SQL is never re-transpiled and serving may use DuckDB.
    """
    if is_duckdb_ready(dashboard_id, db):
        return
    db.add(DashboardDialectMigration(dashboard_id=dashboard_id, status="born_duckdb", widget_rewrites=[]))
    db.commit()


def migrate_dashboard(dashboard, *, dry_run: bool = False, db) -> DashboardMigrationOutcome:
    """Transpile one dashboard's widgets BQ→DuckDB and journal the cutover.

    Idempotent — a dashboard already journaled is skipped (re-transpiling
    DuckDB SQL as BigQuery would corrupt it). Un-transpilable widgets halt the
    dashboard (no write, no journal) for manual review.
    """
    if is_duckdb_ready(dashboard.id, db):
        return DashboardMigrationOutcome(dashboard.id, "skipped")

    widgets = dashboard.widgets or []
    result = transpile_dashboard_widgets(widgets, dry_run=dry_run)

    if not result.ok:
        return DashboardMigrationOutcome(dashboard.id, "halted", result.rewrites, result.unparseable)
    if dry_run:
        return DashboardMigrationOutcome(dashboard.id, "dry_run", result.rewrites)

    dashboard.widgets = widgets  # reassign so the JSONB column flushes
    db.add(dashboard)
    db.add(DashboardDialectMigration(
        dashboard_id=dashboard.id,
        status="migrated",
        widget_rewrites=[{"widget_id": r.widget_id, "old_sql": r.old_sql} for r in result.rewrites],
    ))
    db.commit()
    return DashboardMigrationOutcome(dashboard.id, "migrated", result.rewrites)


def migrate_org(org_id: str, *, dry_run: bool = False, db=None) -> list[DashboardMigrationOutcome]:
    """Cut every dashboard owned by *org_id*'s users over to DuckDB SQL."""
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return migrate_org(org_id, dry_run=dry_run, db=_db)

    from backend.models.dashboard import Dashboard
    from backend.models.user import User

    user_ids = [u.id for u in db.query(User).filter(User.org_id == org_id).all()]
    if not user_ids:
        return []
    dashboards = db.query(Dashboard).filter(Dashboard.user_id.in_(user_ids)).all()
    return [migrate_dashboard(d, dry_run=dry_run, db=db) for d in dashboards]


def rollback_dashboard(dashboard_id: int, *, db=None) -> str:
    """Restore a migrated dashboard's original BigQuery SQL and drop its journal row."""
    if db is None:
        from backend.database.session import SessionLocal
        with SessionLocal() as _db:
            return rollback_dashboard(dashboard_id, db=_db)

    from backend.models.dashboard import Dashboard

    journal = (
        db.query(DashboardDialectMigration)
        .filter(DashboardDialectMigration.dashboard_id == dashboard_id)
        .first()
    )
    if journal is None or journal.status != "migrated":
        return "no_op"  # born_duckdb rows have no original SQL to restore

    old_by_widget = {r["widget_id"]: r["old_sql"] for r in (journal.widget_rewrites or [])}
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if dashboard is not None:
        widgets = dashboard.widgets or []
        for widget in widgets:
            wid = widget.get("id") or widget.get("widgetId")
            ds = widget.get("dataSource")
            if wid in old_by_widget and isinstance(ds, dict):
                ds["sql"] = old_by_widget[wid]
        dashboard.widgets = widgets
        db.add(dashboard)

    db.delete(journal)
    db.commit()
    return "rolled_back"


# ---------------------------------------------------------------------------
# CLI — deliberate per-Org cutover (dry-run + rollback)
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """`python -m backend.migration.dialect_migration --org <id> [--dry-run]`.

    Transpiles every dashboard in the Org from BigQuery to DuckDB stored SQL.
    Halted dashboards (un-transpilable widgets) are reported and left untouched
    for manual review. `--rollback <dashboard_id>` reverses one dashboard.
    """
    import argparse
    from collections import Counter

    parser = argparse.ArgumentParser(description="Phase 3 per-Org BigQuery→DuckDB stored-SQL cutover.")
    parser.add_argument("--org", help="Organization id to migrate")
    parser.add_argument("--dry-run", action="store_true", help="Preview rewrites without writing")
    parser.add_argument("--rollback", type=int, metavar="DASHBOARD_ID", help="Roll back one dashboard")
    args = parser.parse_args(argv)

    if args.rollback is not None:
        print(f"dashboard {args.rollback}: {rollback_dashboard(args.rollback)}")
        return 0

    if not args.org:
        parser.error("--org is required (or use --rollback)")

    outcomes = migrate_org(args.org, dry_run=args.dry_run)
    for o in outcomes:
        line = f"  dashboard {o.dashboard_id}: {o.status}"
        if o.unparseable:
            line += f"  ⚠ un-transpilable widgets: {o.unparseable}"
        elif o.rewrites:
            line += f"  ({len(o.rewrites)} widget(s) rewritten)"
        print(line)

    counts = Counter(o.status for o in outcomes)
    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"\n[{mode}] org={args.org} dashboards={len(outcomes)} {dict(counts)}")
    if counts.get("halted"):
        print("WARNING: halted dashboards have un-transpilable widgets — review before re-running.")
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
