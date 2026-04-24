"""Table Profiler — shared profiling logic used by both Celery tasks and agent tools.

Extracts per-column statistics (min/max/avg, cardinality, top values) from a
database table using a connector.  The connector must already be open and is
*not* closed by this module — the caller manages its lifecycle.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict

from backend.connectors.base import BaseConnector

logger = logging.getLogger(__name__)

NUMERIC_TYPES = frozenset({
    "integer", "bigint", "smallint", "numeric", "decimal", "real",
    "double precision", "float", "int", "tinyint", "mediumint",
    "float4", "float8", "int2", "int4", "int8", "serial", "bigserial",
})
DATE_TYPES = frozenset({
    "date", "timestamp", "timestamp without time zone",
    "timestamp with time zone", "datetime", "timestamptz",
})

MAX_COLUMNS = 30
TOP_VALUES_LIMIT = 5
MAX_DISTINCT_FOR_TOP_VALUES = 100


def _safe(val: Any) -> Any:
    """Convert database-native types to JSON-serializable equivalents."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def profile_table(
    connector: BaseConnector,
    table_name: str,
    schema_name: str | None,
    columns: list[dict],
    row_count: int,
    *,
    db_type: str = "postgres",
    is_dataset: bool = False,
) -> Dict[str, Any]:
    """Profile a single table and return per-column statistics.

    Args:
        connector: Open database connector.
        table_name: Table to profile.
        schema_name: Schema containing the table (e.g. "public"). Ignored for datasets.
        columns: Column definitions from schema discovery (list of {name, type, ...}).
        row_count: Known row count from schema discovery.
        db_type: "postgres" | "mysql" — controls identifier quoting.
        is_dataset: True for SQLite/dataset connections.

    Returns:
        Dict with table_name, row_count, and per-column statistics.
    """
    all_columns = columns[:MAX_COLUMNS]

    def q(name: str) -> str:
        return f"`{name}`" if db_type == "mysql" else f'"{name}"'

    if is_dataset:
        qualified_table = f'"{table_name}"'
    elif schema_name:
        qualified_table = f"{q(schema_name)}.{q(table_name)}"
    else:
        qualified_table = q(table_name)

    # Classify columns by type
    numeric_cols, date_cols, text_cols = [], [], []
    for col in all_columns:
        col_type = col.get("type", "").split("(")[0].strip().lower()
        if col_type in NUMERIC_TYPES:
            numeric_cols.append(col["name"])
        elif col_type in DATE_TYPES:
            date_cols.append(col["name"])
        else:
            text_cols.append(col["name"])

    result_columns: Dict[str, Any] = {}

    # Query A: Numeric stats
    if numeric_cols:
        try:
            parts = []
            for col in numeric_cols:
                qc = q(col)
                parts += [
                    f"MIN({qc})",
                    f"MAX({qc})",
                    f"AVG({qc})",
                    f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END)",
                ]
            res = connector.execute_query(
                f"SELECT {', '.join(parts)} FROM {qualified_table}"
            )
            if res.rows:
                row = res.rows[0]
                for i, col in enumerate(numeric_cols):
                    b = i * 4
                    result_columns[col] = {
                        "type": "numeric",
                        "min": _safe(row[b]),
                        "max": _safe(row[b + 1]),
                        "avg": _safe(row[b + 2]),
                        "null_count": _safe(row[b + 3]),
                    }
        except Exception as e:
            logger.warning("profile_table numeric stats failed for %s: %s", table_name, e)
            for col in numeric_cols:
                result_columns[col] = {"type": "numeric", "error": str(e)}

    # Query B: Date stats
    if date_cols:
        try:
            parts = []
            for col in date_cols:
                qc = q(col)
                parts += [
                    f"MIN({qc})",
                    f"MAX({qc})",
                    f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END)",
                ]
            res = connector.execute_query(
                f"SELECT {', '.join(parts)} FROM {qualified_table}"
            )
            if res.rows:
                row = res.rows[0]
                for i, col in enumerate(date_cols):
                    b = i * 3
                    result_columns[col] = {
                        "type": "date",
                        "min": _safe(row[b]),
                        "max": _safe(row[b + 1]),
                        "null_count": _safe(row[b + 2]),
                    }
        except Exception as e:
            logger.warning("profile_table date stats failed for %s: %s", table_name, e)
            for col in date_cols:
                result_columns[col] = {"type": "date", "error": str(e)}

    # Query C: Categorical distinct counts
    distinct_counts: Dict[str, int] = {}
    if text_cols:
        try:
            parts = []
            for col in text_cols:
                qc = q(col)
                parts += [
                    f"COUNT(DISTINCT {qc})",
                    f"SUM(CASE WHEN {qc} IS NULL THEN 1 ELSE 0 END)",
                ]
            res = connector.execute_query(
                f"SELECT {', '.join(parts)} FROM {qualified_table}"
            )
            if res.rows:
                row = res.rows[0]
                for i, col in enumerate(text_cols):
                    b = i * 2
                    d_count = int(row[b]) if row[b] is not None else 0
                    distinct_counts[col] = d_count
                    result_columns[col] = {
                        "type": "categorical",
                        "distinct_count": d_count,
                        "null_count": _safe(row[b + 1]),
                    }
        except Exception as e:
            logger.warning("profile_table categorical stats failed for %s: %s", table_name, e)
            for col in text_cols:
                result_columns[col] = {"type": "categorical", "error": str(e)}

    # Query D: Top values per categorical column (only if distinct_count <= threshold)
    for col in text_cols:
        d_count = distinct_counts.get(col, 0)
        if d_count == 0 or d_count > MAX_DISTINCT_FOR_TOP_VALUES:
            continue
        try:
            qc = q(col)
            res = connector.execute_query(
                f"SELECT {qc}, COUNT(*) FROM {qualified_table} "
                f"WHERE {qc} IS NOT NULL "
                f"GROUP BY {qc} ORDER BY 2 DESC LIMIT {TOP_VALUES_LIMIT}"
            )
            top_values = [_safe(row[0]) for row in res.rows]
            if col in result_columns:
                result_columns[col]["top_values"] = top_values
        except Exception as e:
            logger.warning("profile_table top values failed for %s.%s: %s", table_name, col, e)

    return {
        "table_name": table_name,
        "row_count": row_count,
        "columns": result_columns,
    }
