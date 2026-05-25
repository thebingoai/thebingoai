"""Shared DuckDB execution helper for DataPlane readers.

Both `LocalFilesystemDataPlane` (dev) and the GCS-httpfs reader (prod, Phase 2)
register views then run already-DuckDB SQL through this one path, so param
binding and the row-cap/truncation parity stay identical across planes.
"""
from __future__ import annotations

import re
import time
from typing import Any

from backend.connectors.base import QueryResult

# DuckDB named placeholder `$name` (name starts with a letter/underscore — `$1`
# numbered-positional placeholders are deliberately excluded).
_NAMED_PARAM_RE = re.compile(r"\$[A-Za-z_]\w*")


def run_duckdb_query(conn, sql: str, params: dict[str, Any] | None = None) -> QueryResult:
    """Execute *sql* on *conn*, binding *params* and capping rows.

    - Named `$name` placeholders (inject_filters duckdb dialect) bind from the
      dict by name; legacy positional `?` / `$1` bind values in order.
    - Caps at `settings.max_query_rows` (fetch one extra to flag truncation),
      matching the source-DB connectors (`base.py`).
    """
    from backend.config import settings

    start = time.time()
    if params:
        if _NAMED_PARAM_RE.search(sql):
            rel = conn.execute(sql, params)
        else:
            rel = conn.execute(sql, list(params.values()))
    else:
        rel = conn.execute(sql)

    columns = [desc[0] for desc in rel.description]
    max_rows = settings.max_query_rows
    rows = rel.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    if truncated:
        rows = rows[:max_rows]

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_time_ms=(time.time() - start) * 1000,
        truncated=truncated,
    )
