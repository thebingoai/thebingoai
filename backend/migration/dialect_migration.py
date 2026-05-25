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

from backend.utils.sql_refs import UntranspilableSQLError, transpile_bq_to_duckdb


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
