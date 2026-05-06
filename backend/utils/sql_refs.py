from __future__ import annotations

import sqlglot
import sqlglot.expressions as exp


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
