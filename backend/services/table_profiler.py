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
    # BigQuery types
    "int64", "float64", "bignumeric",
})
DATE_TYPES = frozenset({
    "date", "timestamp", "timestamp without time zone",
    "timestamp with time zone", "datetime", "timestamptz",
    # BigQuery types
    "time",
})

# BigQuery column types that cannot be profiled with MIN/MAX/COUNT(DISTINCT)
_BQ_SKIP_TYPES = frozenset({"record", "struct", "array", "geography", "json"})

import re as _re

def _bq_partition_where(columns: list[dict]) -> str:
    """Return a WHERE clause for BigQuery profiling queries on partitioned tables.

    Reads the pseudo-columns injected by get_table_schema() to detect the
    partition key, then restricts to the last 90 days so require_partition_filter
    tables don't reject the query.  Returns "" for unpartitioned tables.
    """
    for col in columns:
        ctype = col.get("type", "")
        # Column-based time partition: PARTITION_KEY(col_name)
        m = _re.match(r"PARTITION_KEY\((.+)\)", ctype)
        if m:
            pcol = m.group(1)
            return f"WHERE `{pcol}` >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)"
        # Ingestion-time partition
        if col.get("name") == "_PARTITIONDATE":
            return "WHERE _PARTITIONDATE >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)"
        if col.get("name") == "_PARTITIONTIME":
            return "WHERE DATE(_PARTITIONTIME) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)"
    return ""

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
        db_type: "postgres" | "mysql" | "bigquery" — controls identifier quoting.
        is_dataset: True for SQLite/dataset connections.

    Returns:
        Dict with table_name, row_count, and per-column statistics.
    """
    # BigQuery: wildcard/sharded tables can't be profiled with a direct SELECT
    if db_type == "bigquery" and table_name.endswith("_*"):
        return {"table_name": table_name, "row_count": row_count, "columns": {}}

    all_columns = columns[:MAX_COLUMNS]

    def q(name: str) -> str:
        return f"`{name}`" if db_type in ("mysql", "bigquery") else f'"{name}"'

    if db_type == "bigquery":
        # BigQuery uses backtick-quoted `dataset.table` as a single reference
        if schema_name:
            qualified_table = f"`{schema_name}.{table_name}`"
        else:
            qualified_table = f"`{table_name}`"
    elif is_dataset:
        qualified_table = f'"{table_name}"'
    elif schema_name:
        qualified_table = f"{q(schema_name)}.{q(table_name)}"
    else:
        qualified_table = q(table_name)

    # For BigQuery partitioned tables, build a WHERE clause so queries satisfy
    # require_partition_filter without returning an error.
    bq_where = _bq_partition_where(columns) if db_type == "bigquery" else ""

    # Classify columns by type; skip pseudo-columns and unsupported BQ types
    numeric_cols, date_cols, text_cols = [], [], []
    for col in all_columns:
        if db_type == "bigquery" and col["name"].startswith("_"):
            continue  # skip _TABLE_SUFFIX, _PARTITIONTIME, __bq_partition_field__ etc.
        col_type = col.get("type", "").split("(")[0].strip().lower()
        if db_type == "bigquery" and col_type in _BQ_SKIP_TYPES:
            continue  # RECORD/STRUCT/ARRAY can't be profiled with scalar functions
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
                f"SELECT {', '.join(parts)} FROM {qualified_table} {bq_where}".strip()
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
                f"SELECT {', '.join(parts)} FROM {qualified_table} {bq_where}".strip()
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
                f"SELECT {', '.join(parts)} FROM {qualified_table} {bq_where}".strip()
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
            extra_and = f"AND {qc} IS NOT NULL" if bq_where else f"WHERE {qc} IS NOT NULL"
            res = connector.execute_query(
                f"SELECT {qc}, COUNT(*) FROM {qualified_table} "
                f"{bq_where} {extra_and} "
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
