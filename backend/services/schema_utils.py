"""Shared schema utilities for SQL fix suggestions and schema summaries."""
import re


def extract_table_names(sql: str) -> set:
    """Extract table names referenced after FROM/JOIN keywords."""
    pattern = re.compile(r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_.]*)', re.IGNORECASE)
    return {m.group(1).lower() for m in pattern.finditer(sql)}


def build_schema_summary(schema_json: dict, referenced_tables: set) -> str:
    """Build a concise text summary of schema tables relevant to the SQL query."""
    lines = []

    # Support two schema formats:
    # 1. Flat: {"tables": [...]}
    # 2. Nested: {"schemas": {"public": {"tables": {"name": {"columns": [...]}}}}}
    flat_tables = schema_json.get('tables', [])
    if flat_tables:
        tables_list = flat_tables
    else:
        tables_list = []
        for schema_name, schema_body in schema_json.get('schemas', {}).items():
            for table_name, table_body in schema_body.get('tables', {}).items():
                cols = table_body.get('columns', [])
                if isinstance(cols, list):
                    columns = [{'name': c.get('name', c) if isinstance(c, dict) else c,
                                'data_type': c.get('type', c.get('data_type', '')) if isinstance(c, dict) else ''} for c in cols]
                else:
                    columns = [{'name': k, 'data_type': v.get('type', v.get('data_type', '')) if isinstance(v, dict) else ''}
                               for k, v in cols.items()]
                tables_list.append({
                    'name': table_name,
                    'row_count': table_body.get('row_count', '?'),
                    'columns': columns,
                })

    all_table_names = [t.get('name', '') for t in tables_list]
    lines.append(f"Available tables: {', '.join(all_table_names)}")
    lines.append("")

    filtered = [t for t in tables_list if t.get('name', '').lower() in referenced_tables]
    if not filtered:
        filtered = tables_list[:10]

    for table in filtered:
        name = table.get('name', '')
        row_count = table.get('row_count', '?')
        columns = table.get('columns', [])
        col_summary = ', '.join(
            f"{c.get('name')} ({c.get('data_type', 'unknown')})" for c in columns
        )
        lines.append(f"Table: {name} ({row_count} rows)")
        lines.append(f"  Columns: {col_summary}")

    relationships = schema_json.get('relationships', [])
    if relationships and isinstance(relationships, list):
        lines.append("Relationships: " + '; '.join(
            f"{r.get('from_table')}.{r.get('from_column')} -> {r.get('to_table')}.{r.get('to_column')}"
            for r in relationships
            if r.get('from_table', '').lower() in referenced_tables or r.get('to_table', '').lower() in referenced_tables
        ))

    return '\n'.join(lines)
