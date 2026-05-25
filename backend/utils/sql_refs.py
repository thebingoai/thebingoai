from __future__ import annotations

import functools

import sqlglot
import sqlglot.expressions as exp


class UntranspilableSQLError(ValueError):
    """Raised when BigQuery SQL cannot be safely transpiled to DuckDB.

    Carries the offending SQL and a human reason so the Phase 3 migration can
    queue the widget for manual review instead of persisting broken DuckDB SQL.
    """

    def __init__(self, sql: str, reason: str) -> None:
        self.sql = sql
        self.reason = reason
        super().__init__(f"Cannot transpile BigQuery SQL to DuckDB: {reason}")


@functools.lru_cache(maxsize=1)
def _duckdb_function_names() -> frozenset[str]:
    """Lower-cased names of every function DuckDB knows about (cached).

    Used to detect BigQuery functions that sqlglot leaves unmapped — if such a
    function isn't in DuckDB's catalog, running the transpiled SQL would fail,
    so we raise instead of emitting it silently.
    """
    import duckdb

    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT DISTINCT lower(function_name) FROM duckdb_functions()"
        ).fetchall()
        return frozenset(r[0] for r in rows if r[0])
    finally:
        con.close()


def _unknown_duckdb_functions(ast: exp.Expression) -> set[str]:
    """Return function names in *ast* that DuckDB has no definition for.

    Only `exp.Anonymous` nodes are checked — sqlglot renders functions it knows
    how to map as typed nodes, so anything left Anonymous is a function name it
    passed through verbatim. If DuckDB doesn't have that name, it's a gap.
    """
    catalog = _duckdb_function_names()
    unknown: set[str] = set()
    for node in ast.find_all(exp.Anonymous):
        name = (node.name or "").lower()
        if name and name not in catalog:
            unknown.add(name)
    return unknown


def transpile_bq_to_duckdb(sql: str) -> str:
    """Transpile a single BigQuery SQL statement to DuckDB, or raise.

    Steps (each failure raises `UntranspilableSQLError` with a reason):
      1. Parse as BigQuery (backticks, DATE_TRUNC(col, unit), SAFE_*, etc.).
      2. Render in the DuckDB dialect (backticks→double-quotes, arg reorder,
         SAFE_CAST→TRY_CAST handled by sqlglot).
      3. Re-parse the output as DuckDB — catches any syntactically-invalid output.
      4. Reject output containing functions absent from DuckDB's catalog
         (BigQuery-only funcs sqlglot couldn't map, e.g. APPROX_QUANTILES).

    NOT used on the hot read path — this drives the Phase 3 stored-SQL migration
    and its validation. The read path runs already-DuckDB SQL.
    """
    try:
        ast = sqlglot.parse_one(sql, read="bigquery", error_level=sqlglot.ErrorLevel.RAISE)
    except UntranspilableSQLError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UntranspilableSQLError(sql, f"BigQuery parse failed: {e}") from e

    try:
        out = ast.sql(dialect="duckdb")
    except Exception as e:  # noqa: BLE001
        raise UntranspilableSQLError(sql, f"DuckDB generation failed: {e}") from e

    try:
        out_ast = sqlglot.parse_one(out, read="duckdb", error_level=sqlglot.ErrorLevel.RAISE)
    except Exception as e:  # noqa: BLE001
        raise UntranspilableSQLError(sql, f"transpiled output is not valid DuckDB: {e}") from e

    unknown = _unknown_duckdb_functions(out_ast)
    if unknown:
        raise UntranspilableSQLError(
            sql, f"function(s) unsupported by DuckDB: {', '.join(sorted(unknown))}"
        )

    return out


def extract_table_refs(sql: str) -> list[str]:
    """Return list of table names referenced in *sql* (lower-cased, deduplicated, sorted).
    Returns [] on parse failure."""
    try:
        parsed = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception:
        return []

    tables = set()
    for node in parsed.find_all(exp.Table):
        if node.name:
            tables.add(node.name.lower())

    return sorted(list(tables))


def rewrite_table_refs(sql: str, mapping: dict[str, str]) -> tuple[str, bool]:
    """Rewrite table references in *sql* using *mapping* (old_name → new_name, case-insensitive).
    Returns (rewritten_sql, success). success=False if sql could not be parsed."""
    try:
        parsed = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception:
        return (sql, False)

    normalized_mapping = {k.lower(): v for k, v in mapping.items()}

    def _rewriter(node: exp.Expression) -> exp.Expression:
        if isinstance(node, exp.Table) and node.name and node.name.lower() in normalized_mapping:
            new_name = normalized_mapping[node.name.lower()]
            new_node = node.copy()
            new_node.this.args["this"] = new_name  # mutate the Identifier's raw string
            return new_node
        return node

    try:
        rewritten = parsed.transform(_rewriter)
        return (rewritten.sql(), True)
    except Exception:
        return (sql, False)


def can_parse(sql: str) -> bool:
    """Return True if sqlglot can parse *sql* without errors."""
    try:
        sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
        return True
    except Exception:
        return False
