"""
SQL Validation — pure functions for cross-referencing widget SQL against database schemas.

Extracted from dashboard_tools._validate_widget_sql_schema to reduce complexity.
All functions are stateless and accept explicit parameters (no closures).
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# Module-level compiled regex patterns
# ---------------------------------------------------------------------------

# Extracts table names and optional aliases from FROM / JOIN clauses.
# Negative lookahead prevents greedy alias capture from consuming SQL keywords.
TABLE_ALIAS_RE = re.compile(
    r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_.]*)'
    r'(?:\s+(?:AS\s+)?'
    r'(?!(?:JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|NATURAL|ON|WHERE|GROUP|ORDER|HAVING|LIMIT|SET|AND|OR|USING)\b)'
    r'([a-zA-Z_][a-zA-Z0-9_]*))?',
    re.IGNORECASE,
)

# Extracts CTE names from WITH ... AS (...) clauses (including RECURSIVE).
CTE_NAME_RE = re.compile(
    r'(?:\bWITH\b\s+(?:RECURSIVE\s+)?)([a-zA-Z_]\w*)\s+AS\s*\('
    r'|,\s*([a-zA-Z_]\w*)\s+AS\s*\(',
    re.IGNORECASE,
)

# Extracts column-bearing clauses from SQL (SELECT..FROM, WHERE, GROUP BY, etc.)
CLAUSE_RE = re.compile(
    r'SELECT\s+(.*?)\s+FROM\b'
    r'|WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+HAVING|\s+LIMIT|$)'
    r'|GROUP\s+BY\s+(.*?)(?:\s+HAVING|\s+ORDER\s+BY|\s+LIMIT|$)'
    r'|ORDER\s+BY\s+(.*?)(?:\s+LIMIT|$)'
    r'|HAVING\s+(.*?)(?:\s+ORDER\s+BY|\s+LIMIT|$)',
    re.IGNORECASE | re.DOTALL,
)

# Extracts AS <alias> from SELECT clauses for output column aliases.
ALIAS_RE = re.compile(r'\bAS\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE)

# SQL keywords to exclude from column candidate detection.
SQL_KEYWORDS = frozenset({
    "select", "from", "where", "group", "by", "order", "having", "join",
    "left", "right", "inner", "outer", "full", "on", "as", "and", "or",
    "not", "in", "is", "null", "true", "false", "distinct", "limit",
    "offset", "union", "all", "case", "when", "then", "else", "end",
    "between", "like", "ilike", "exists", "asc", "desc", "with",
    "recursive", "filter", "within", "rows", "range",
})

# SQL functions to exclude from column candidate detection.
SQL_FUNCTIONS = frozenset({
    "count", "sum", "avg", "min", "max", "coalesce", "nullif", "cast",
    "to_char", "to_date", "to_number", "extract", "date_part", "now",
    "current_date", "current_timestamp", "replace", "trim", "lower",
    "upper", "length", "substring", "concat", "round", "floor", "ceil",
    "abs", "mod", "greatest", "least", "row_number", "rank", "dense_rank",
    "lag", "lead", "first_value", "last_value", "over", "partition",
    "interval", "date_trunc", "generate_series", "unnest", "array_agg",
    "string_agg", "json_agg", "jsonb_agg",
    "percent_rank", "cume_dist", "ntile", "nth_value",
    "preceding", "following", "unbounded",
})

# Keywords that should never be treated as table aliases.
JOIN_KEYWORDS = frozenset({
    "on", "where", "group", "order", "having", "limit", "left",
    "right", "inner", "outer", "full", "cross", "natural", "join",
    "set", "returning", "using", "and", "or",
})


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def get_tables_dict(schema_json: dict) -> Any:
    """Extract {table_name: {columns: [...]}} or [...] from flat or nested schema format."""
    tables = schema_json.get("tables", {})
    if tables:
        return tables
    # Nested: {"schemas": {"public": {"tables": {...}}}}
    for schema_data in schema_json.get("schemas", {}).values():
        if isinstance(schema_data, dict) and "tables" in schema_data:
            return schema_data["tables"]
    return {}


def get_table_columns(schema_json: dict, table_name: str) -> set[str]:
    """Return lowercase column names for a table from the schema."""
    tables = get_tables_dict(schema_json)
    if not tables:
        return set()
    # Flat format: [{"name": "...", "columns": [...]}]
    if isinstance(tables, list):
        for t in tables:
            if t.get("name", "").lower() == table_name.lower():
                cols = t.get("columns", [])
                return {
                    (c["name"].lower() if isinstance(c, dict) else c.lower())
                    for c in cols
                }
    # Dict format: {"tableName": {"columns": [...]}}
    elif isinstance(tables, dict):
        for tname, tdata in tables.items():
            if tname.lower() == table_name.lower():
                cols = tdata.get("columns", []) if isinstance(tdata, dict) else []
                return {
                    (c["name"].lower() if isinstance(c, dict) else c.lower())
                    for c in cols
                }
    return set()


def get_all_tables(schema_json: dict) -> set[str]:
    """Return lowercase set of all table names in the schema."""
    tables = get_tables_dict(schema_json)
    if isinstance(tables, list):
        return {t.get("name", "").lower() for t in tables if t.get("name")}
    elif isinstance(tables, dict):
        return {t.lower() for t in tables}
    return set()


# ---------------------------------------------------------------------------
# SQL parsing helpers
# ---------------------------------------------------------------------------

def extract_cte_names(sql: str) -> set[str]:
    """Extract CTE names from a SQL string."""
    cte_names: set[str] = set()
    for m in CTE_NAME_RE.finditer(sql):
        name = m.group(1) or m.group(2)
        if name:
            cte_names.add(name.lower())
    return cte_names


def extract_table_refs(sql: str) -> tuple[list[str], set[str]]:
    """
    Extract table names and aliases from FROM/JOIN clauses.

    Returns:
        (table_matches, table_aliases) where table_matches is the raw list of
        table name strings and table_aliases is a lowercase set of alias names.
    """
    matches = TABLE_ALIAS_RE.findall(sql)
    if not matches:
        return [], set()
    table_matches = [m[0] for m in matches]
    table_aliases = {
        m[1].lower() for m in matches
        if m[1] and m[1].lower() not in JOIN_KEYWORDS
    }
    return table_matches, table_aliases


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_tables(
    table_matches: list[str],
    known_virtual: set[str],
    all_schema_tables: set[str],
    widget_id: str,
) -> list[str]:
    """
    Validate that all referenced tables exist in the schema.
    Returns list of warning strings. Empty list means all tables are valid.
    """
    warnings = []
    for tbl_match in table_matches:
        tbl_name = tbl_match.split(".")[-1]
        if tbl_name.lower() in known_virtual:
            continue
        if all_schema_tables and tbl_name.lower() not in all_schema_tables:
            warnings.append(
                f"Widget '{widget_id}': table '{tbl_name}' not found in schema. "
                f"Available tables: {', '.join(sorted(all_schema_tables))}"
            )
    return warnings


def validate_sql_columns(
    sql: str,
    schema_json: dict,
    table_matches: list[str],
    table_aliases: set[str],
    all_schema_tables: set[str],
    widget_id: str,
) -> list[str]:
    """
    Validate that SQL column references exist in the merged column set of all
    referenced tables. Returns list of warning strings.
    """
    all_joined_tables = [m.split(".")[-1] for m in table_matches]
    merged_columns: set[str] = set()
    for tbl in all_joined_tables:
        merged_columns |= get_table_columns(schema_json, tbl)

    if not merged_columns:
        return []

    # Extract column-bearing clauses
    clause_text = " ".join(
        part for m in CLAUSE_RE.finditer(sql) for part in m.groups() if part
    )

    # Strip quoted identifiers
    clause_text = re.sub(r'"[^"]*"', '', clause_text)
    clause_text = re.sub(r'\[[^\]]*\]', '', clause_text)
    # Remove AS <alias>
    clause_text = re.sub(r'\bAS\s+[a-zA-Z_][a-zA-Z0-9_]*', '', clause_text, flags=re.IGNORECASE)
    # Strip table alias dot-prefixes
    for _alias in table_aliases:
        clause_text = re.sub(rf'\b{re.escape(_alias)}\.', '', clause_text)

    raw_identifiers = re.findall(r'\b([a-z_][a-z0-9_]*)\b', clause_text.lower())
    candidate_columns = {
        tok for tok in raw_identifiers
        if tok not in SQL_KEYWORDS
        and tok not in SQL_FUNCTIONS
        and not tok.isdigit()
    }

    # Exclude table names and aliases
    candidate_columns -= {t.lower() for t in all_joined_tables}
    candidate_columns -= all_schema_tables
    candidate_columns -= table_aliases

    bad_sql_columns = [c for c in sorted(candidate_columns) if c not in merged_columns]
    if bad_sql_columns:
        tables_checked = ", ".join(all_joined_tables)
        return [
            f"Widget '{widget_id}': SQL references column(s) {bad_sql_columns} "
            f"that do not exist in table(s) '{tables_checked}'. "
            f"Available columns: {', '.join(sorted(merged_columns))}"
        ]
    return []


def validate_mapping_columns(
    sql: str,
    mapping: dict,
    widget_type: str,
    schema_json: dict,
    table_matches: list[str],
    referenced_table: str,
    widget_id: str,
) -> list[str]:
    """
    Validate that mapping columns reference valid SQL output columns.
    Returns list of warning strings.
    """
    all_joined_tables = [m.split(".")[-1] for m in table_matches]
    merged_columns: set[str] = set()
    for tbl in all_joined_tables:
        merged_columns |= get_table_columns(schema_json, tbl)

    # Extract SQL output aliases
    sql_aliases = {m.group(1).lower() for m in ALIAS_RE.finditer(sql)}
    valid_output_cols = merged_columns | sql_aliases

    # Extract mapping columns to validate
    mapping_columns: list[str] = []
    mapping_type = mapping.get("type")
    if mapping_type == "kpi":
        for field in ("valueColumn", "trendValueColumn", "sparklineXColumn", "sparklineYColumn", "sparklineSortColumn"):
            if mapping.get(field):
                mapping_columns.append(mapping[field])
    elif mapping_type == "chart":
        if mapping.get("labelColumn"):
            mapping_columns.append(mapping["labelColumn"])
        for ds_col in mapping.get("datasetColumns", []):
            if isinstance(ds_col, dict) and ds_col.get("column"):
                mapping_columns.append(ds_col["column"])
    elif mapping_type == "table":
        for col_cfg in mapping.get("columnConfig", []):
            if isinstance(col_cfg, dict) and col_cfg.get("column"):
                mapping_columns.append(col_cfg["column"])

    bad_columns = [c for c in mapping_columns if c.lower() not in valid_output_cols]
    if bad_columns:
        return [
            f"Widget '{widget_id}': mapping column(s) {bad_columns} not found in "
            f"SQL output or table '{referenced_table}'. "
            f"Available output columns: {', '.join(sorted(valid_output_cols))}"
        ]
    return []
