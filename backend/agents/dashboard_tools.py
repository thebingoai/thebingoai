"""
Dashboard Tools — LangChain tool builders for dashboard creation.

Kept as a standalone module to avoid circular imports between graph.py and tool_registry.py.
"""
from typing import List, Callable
from backend.agents.context import AgentContext
from backend.connectors.factory import get_connector_for_connection
import json
import logging

logger = logging.getLogger(__name__)

_VALID_WIDGET_TYPES = {"kpi", "chart", "table", "text", "filter"}
_DATA_WIDGET_TYPES = {"kpi", "chart", "table"}
_VALID_MAPPING_TYPES = {"kpi", "chart", "table"}


def _validate_data_source(data_source: dict, widget_type: str, widget_index: int) -> str | None:
    """Validate optional dataSource field. Returns error message or None if valid."""
    if not isinstance(data_source, dict):
        return f"Widget at index {widget_index}: dataSource must be an object"

    if "connectionId" not in data_source:
        return f"Widget at index {widget_index}: dataSource missing required field: connectionId"
    if not isinstance(data_source["connectionId"], int):
        return f"Widget at index {widget_index}: dataSource.connectionId must be an integer"

    if "sql" not in data_source:
        return f"Widget at index {widget_index}: dataSource missing required field: sql"
    if not isinstance(data_source["sql"], str) or not data_source["sql"].strip():
        return f"Widget at index {widget_index}: dataSource.sql must be a non-empty string"

    if "mapping" not in data_source:
        return f"Widget at index {widget_index}: dataSource missing required field: mapping"
    mapping = data_source["mapping"]
    if not isinstance(mapping, dict):
        return f"Widget at index {widget_index}: dataSource.mapping must be an object"

    mapping_type = mapping.get("type")
    if mapping_type not in _VALID_MAPPING_TYPES:
        return (
            f"Widget at index {widget_index}: dataSource.mapping.type must be one of "
            f"{sorted(_VALID_MAPPING_TYPES)}"
        )
    if mapping_type != widget_type:
        return (
            f"Widget at index {widget_index}: dataSource.mapping.type '{mapping_type}' "
            f"must match widget.type '{widget_type}'"
        )

    return None


def _validate_widgets(widgets: list) -> str | None:
    """Validate widget list. Returns error message or None if valid."""
    for i, widget in enumerate(widgets):
        if not isinstance(widget, dict):
            return f"Widget at index {i} must be an object"
        if "id" not in widget:
            return f"Widget at index {i} missing required field: id"
        if "position" not in widget:
            return f"Widget at index {i} missing required field: position"
        if "widget" not in widget:
            return f"Widget at index {i} missing required field: widget"

        position = widget["position"]
        if not isinstance(position, dict):
            return f"Widget at index {i}: position must be an object"
        for field in ("x", "y", "w", "h"):
            if field not in position:
                return f"Widget at index {i}: position missing required field: {field}"

        widget_config = widget["widget"]
        if not isinstance(widget_config, dict):
            return f"Widget at index {i}: widget must be an object"
        if "type" not in widget_config:
            return f"Widget at index {i}: widget missing required field: type"
        if widget_config["type"] not in _VALID_WIDGET_TYPES:
            return f"Widget at index {i}: widget.type must be one of {sorted(_VALID_WIDGET_TYPES)}"

        # Validate optional dataSource for data widgets
        if "dataSource" in widget:
            error = _validate_data_source(widget["dataSource"], widget_config["type"], i)
            if error:
                return error

    return None


def _validate_widget_sql_schema(widgets: list) -> list[str]:
    """
    Cross-reference widget SQL mapping columns against the schema for each connectionId.
    Returns a list of warning strings. Empty list means no issues found.
    """
    from backend.services.schema_discovery import load_schema_file
    import re

    # Collect unique connection IDs
    connection_ids = {
        w["dataSource"]["connectionId"]
        for w in widgets
        if "dataSource" in w
    }

    # Load schemas
    schemas: dict[int, dict] = {}
    for cid in connection_ids:
        try:
            schemas[cid] = load_schema_file(cid)
        except FileNotFoundError:
            pass  # Schema not cached — skip validation for this connection

    if not schemas:
        return []

    def _get_tables_dict(schema_json: dict) -> dict:
        """Extract {table_name: {columns: [...]}} from flat or nested schema format."""
        # Flat: {"tables": {...}} or {"tables": [...]}
        tables = schema_json.get("tables", {})
        if tables:
            return tables
        # Nested: {"schemas": {"public": {"tables": {...}}}}
        for schema_data in schema_json.get("schemas", {}).values():
            if isinstance(schema_data, dict) and "tables" in schema_data:
                return schema_data["tables"]
        return {}

    def _get_table_columns(schema_json: dict, table_name: str) -> set[str]:
        """Return lowercase column names for a table from the schema."""
        tables = _get_tables_dict(schema_json)
        if not tables:
            return set()
        # Flat format: {"tables": [{"name": "...", "columns": [...]}]}
        if isinstance(tables, list):
            for t in tables:
                if t.get("name", "").lower() == table_name.lower():
                    cols = t.get("columns", [])
                    return {
                        (c["name"].lower() if isinstance(c, dict) else c.lower())
                        for c in cols
                    }
        # Dict format: {"tables": {"tableName": {"columns": [...]}}}
        elif isinstance(tables, dict):
            for tname, tdata in tables.items():
                if tname.lower() == table_name.lower():
                    cols = tdata.get("columns", []) if isinstance(tdata, dict) else []
                    return {
                        (c["name"].lower() if isinstance(c, dict) else c.lower())
                        for c in cols
                    }
        return set()

    def _get_all_tables(schema_json: dict) -> set[str]:
        tables = _get_tables_dict(schema_json)
        if isinstance(tables, list):
            return {t.get("name", "").lower() for t in tables if t.get("name")}
        elif isinstance(tables, dict):
            return {t.lower() for t in tables}
        return set()

    warnings = []
    for w in widgets:
        if "dataSource" not in w:
            continue
        ds = w["dataSource"]
        cid = ds["connectionId"]
        sql = ds.get("sql", "")
        mapping = ds.get("mapping", {})
        widget_id = w.get("id", "?")

        schema_json = schemas.get(cid)
        if not schema_json:
            continue

        # Extract table names referenced in SQL (FROM / JOIN)
        table_matches = re.findall(r'\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_.]*)', sql, re.IGNORECASE)
        if not table_matches:
            continue

        all_schema_tables = _get_all_tables(schema_json)
        referenced_table = table_matches[0].split(".")[-1]  # Handle schema.table notation

        # Validate first referenced table exists
        if all_schema_tables and referenced_table.lower() not in all_schema_tables:
            warnings.append(
                f"Widget '{widget_id}': table '{referenced_table}' not found in schema. "
                f"Available tables: {', '.join(sorted(all_schema_tables))}"
            )
            continue

        # Build merged column set across all referenced tables (handles JOINs)
        all_joined_tables = [m.split(".")[-1] for m in table_matches]
        merged_columns: set[str] = set()
        for tbl in all_joined_tables:
            merged_columns |= _get_table_columns(schema_json, tbl)

        if not merged_columns:
            continue

        # --- SQL column validation ---
        # SQL keywords, functions, and common literals to exclude from column checks
        _SQL_KEYWORDS = {
            "select", "from", "where", "group", "by", "order", "having", "join",
            "left", "right", "inner", "outer", "full", "on", "as", "and", "or",
            "not", "in", "is", "null", "true", "false", "distinct", "limit",
            "offset", "union", "all", "case", "when", "then", "else", "end",
            "between", "like", "ilike", "exists", "asc", "desc", "with",
        }
        _SQL_FUNCTIONS = {
            "count", "sum", "avg", "min", "max", "coalesce", "nullif", "cast",
            "to_char", "to_date", "to_number", "extract", "date_part", "now",
            "current_date", "current_timestamp", "replace", "trim", "lower",
            "upper", "length", "substring", "concat", "round", "floor", "ceil",
            "abs", "mod", "greatest", "least", "row_number", "rank", "dense_rank",
            "lag", "lead", "first_value", "last_value", "over", "partition",
            "interval", "date_trunc", "generate_series", "unnest", "array_agg",
            "string_agg", "json_agg", "jsonb_agg",
        }

        # Extract column-bearing clauses: SELECT ... FROM, WHERE ..., GROUP BY ..., ORDER BY ..., HAVING ...
        clause_pattern = re.compile(
            r'SELECT\s+(.*?)\s+FROM\b'
            r'|WHERE\s+(.*?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+HAVING|\s+LIMIT|$)'
            r'|GROUP\s+BY\s+(.*?)(?:\s+HAVING|\s+ORDER\s+BY|\s+LIMIT|$)'
            r'|ORDER\s+BY\s+(.*?)(?:\s+LIMIT|$)'
            r'|HAVING\s+(.*?)(?:\s+ORDER\s+BY|\s+LIMIT|$)',
            re.IGNORECASE | re.DOTALL,
        )
        clause_text = " ".join(
            part for m in clause_pattern.finditer(sql) for part in m.groups() if part
        )

        # Extract bare identifiers, skipping aliases defined with AS
        # Remove AS <alias> to avoid alias names being treated as column refs
        clause_text = re.sub(r'\bAS\s+[a-zA-Z_][a-zA-Z0-9_]*', '', clause_text, flags=re.IGNORECASE)

        raw_identifiers = re.findall(r'\b([a-z_][a-z0-9_]*)\b', clause_text.lower())
        candidate_columns = {
            tok for tok in raw_identifiers
            if tok not in _SQL_KEYWORDS
            and tok not in _SQL_FUNCTIONS
            and not tok.isdigit()
            # Skip table alias references (e.g. "t1" followed by ".col" is handled by extracting the col part)
        }

        # Also exclude table names themselves (they appear in JOINs/subqueries)
        candidate_columns -= {t.lower() for t in all_joined_tables}
        candidate_columns -= all_schema_tables  # table names used as schema-qualified refs

        bad_sql_columns = [c for c in sorted(candidate_columns) if c not in merged_columns]
        if bad_sql_columns:
            tables_checked = ", ".join(all_joined_tables)
            warnings.append(
                f"Widget '{widget_id}': SQL references column(s) {bad_sql_columns} "
                f"that do not exist in table(s) '{tables_checked}'. "
                f"Available columns: {', '.join(sorted(merged_columns))}"
            )
            continue  # Skip mapping validation for this widget — fix SQL first

        # --- Mapping column validation (against SQL aliases / result columns) ---
        # Get columns for the primary table (for mapping alias check)
        table_columns = _get_table_columns(schema_json, referenced_table)

        # Extract SQL output aliases (SELECT ... AS alias)
        alias_pattern = re.compile(r'\bAS\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE)
        sql_aliases = {m.group(1).lower() for m in alias_pattern.finditer(sql)}
        # Mapping columns are aliases in the SQL output, not raw table columns
        valid_output_cols = merged_columns | sql_aliases

        # Extract mapping columns to validate
        mapping_columns = []
        mapping_type = mapping.get("type")
        if mapping_type == "kpi":
            for field in ("valueColumn", "trendValueColumn", "sparklineColumn"):
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
            warnings.append(
                f"Widget '{widget_id}': mapping column(s) {bad_columns} not found in "
                f"SQL output or table '{referenced_table}'. "
                f"Available output columns: {', '.join(sorted(valid_output_cols))}"
            )

    return warnings


async def _attempt_sql_fix(
    sql: str,
    error_message: str,
    connection,
    mapping: dict,
    widget_id: str,
    widget_title: str | None = None,
) -> str | None:
    """Use LLM to fix a broken SQL query. Returns corrected SQL or None."""
    import re
    from backend.services.schema_discovery import load_schema_file
    from backend.services.schema_utils import extract_table_names, build_schema_summary
    from backend.llm.factory import get_provider
    from backend.config import settings

    schema_summary = ""
    try:
        schema_json = load_schema_file(connection.id)
        referenced_tables = extract_table_names(sql)
        schema_summary = build_schema_summary(schema_json, referenced_tables)
    except FileNotFoundError:
        logger.warning(f"Widget '{widget_id}': schema file not found for connection {connection.id}, fixing without schema")

    mapping_info = ', '.join(f"{k}={v}" for k, v in mapping.items() if k != 'type')
    mapping_type = mapping.get('type', 'unknown')

    title_context = f"\nWidget title: {widget_title}" if widget_title else ""

    prompt = f"""You are a SQL expert. Fix the SQL query that produced an error.

Original SQL:
```sql
{sql}
```

Error:
{error_message}

Widget type: {mapping_type}
Expected output columns: {mapping_info}
Database type: {connection.db_type}{title_context}
IMPORTANT: Only use table and column names that exist in the schema below. Do NOT invent table or column names.
"""

    if title_context:
        prompt += """
SEMANTIC CHECK: The fixed SQL must correctly query data that matches the widget title.
For example, if the title says "Average Price", the SQL must query a price-related column — not floor_area, size, or other unrelated columns.
"""

    if schema_summary:
        prompt += f"\nDatabase schema:\n{schema_summary}\n"

    prompt += """
SQL validation rules (your output must comply):
- Query must start with SELECT or WITH (single statement only)
- Forbidden keywords: INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, GRANT, REVOKE, EXEC, EXECUTE, COPY, LOAD, SET, CALL, RENAME
- String functions like REPLACE(), SUBSTRING(), TRIM() are allowed

Return ONLY a JSON object with this exact structure (no markdown, no extra text):
{"suggested_sql": "...", "explanation": "..."}

The explanation should be one sentence describing what was wrong and what was changed."""

    try:
        provider = get_provider(settings.default_llm_provider)
        messages = [{"role": "user", "content": prompt}]
        response = await provider.chat(messages, temperature=0.2)
        content = response.strip()

        if content.startswith("```"):
            content = re.sub(r'^```[a-z]*\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
            content = content.strip()

        result = json.loads(content)
        return result.get("suggested_sql")
    except Exception as e:
        logger.warning(f"Widget '{widget_id}': LLM SQL fix attempt failed: {e}")
        return None


async def _execute_widget_sql(widget: dict, db_session_factory: Callable) -> None:
    """
    Execute the dataSource SQL for a widget and merge results into widget.widget.config.

    Modifies widget in-place. On first failure, attempts an LLM-powered SQL fix and retries once.
    Errors are logged but not raised — the widget is left with whatever config was provided
    by the LLM if both attempts fail.
    """
    from backend.models.database_connection import DatabaseConnection
    from backend.services.widget_transform import transform_widget_data

    data_source = widget.get("dataSource")
    if not data_source:
        return

    connection_id = data_source.get("connectionId")
    sql = data_source.get("sql")
    mapping = data_source.get("mapping")
    widget_id = widget.get("id")
    widget_title = widget.get("widget", {}).get("config", {}).get("title") or widget.get("widget", {}).get("config", {}).get("label")

    db = db_session_factory()
    connector = None
    try:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
        ).first()
        if not connection:
            logger.warning(f"Widget '{widget_id}': connection {connection_id} not found, skipping SQL execution")
            return

        connector = get_connector_for_connection(connection)

        try:
            result = connector.execute_query(sql)
            config = transform_widget_data(result, mapping)
            widget["widget"]["config"].update(config)
            logger.info(f"Widget '{widget_id}': SQL executed, config populated with {result.row_count} rows")
            return
        except Exception as e:
            first_error_msg = str(e)
            logger.warning(f"Widget '{widget_id}': SQL execution failed, attempting LLM fix: {first_error_msg}")

        # Attempt LLM-powered SQL fix
        fixed_sql = await _attempt_sql_fix(
            sql=sql,
            error_message=first_error_msg,
            connection=connection,
            mapping=mapping,
            widget_id=widget_id,
            widget_title=widget_title,
        )

        if not fixed_sql:
            logger.warning(f"Widget '{widget_id}': LLM fix returned no SQL, using LLM-provided config")
            return

        logger.info(f"Widget '{widget_id}': SQL fix attempted, retrying with corrected SQL")
        try:
            result = connector.execute_query(fixed_sql)
            config = transform_widget_data(result, mapping)
            widget["widget"]["config"].update(config)
            # Persist the fixed SQL back to the widget's dataSource
            data_source["sql"] = fixed_sql
            logger.info(f"Widget '{widget_id}': SQL fix succeeded, config populated with {result.row_count} rows")
        except Exception as retry_error:
            logger.warning(f"Widget '{widget_id}': SQL fix also failed, using LLM-provided config. Original: {first_error_msg} | Retry: {retry_error}")
    finally:
        if connector:
            connector.close()
        db.close()


def build_dashboard_tools(context: AgentContext, db_session_factory: Callable) -> List:
    """Return [create_dashboard] tool bound to context and db_session_factory."""
    if db_session_factory is None:
        return []

    from langchain_core.tools import tool
    from backend.models.dashboard import Dashboard

    @tool
    async def create_dashboard(title: str, description: str, widgets_json: str) -> str:
        """
        Create a new dashboard with widgets and persist it to the database.

        For SQL-backed widgets (chart/kpi/table with a dataSource field), the tool
        automatically executes the SQL and populates widget.config with live data.
        You only need to provide the SQL, mapping, and minimal config fields
        (chart type, title, KPI label, table column definitions, etc.).
        SQL execution errors are non-fatal — the dashboard is still created with
        whatever config you provided.

        Args:
            title: Dashboard title (e.g. "Property Overview Dashboard")
            description: Brief description of what the dashboard shows
            widgets_json: JSON array of widget objects. CRITICAL: each widget.widget must have
                a nested "config" sub-object. Layout uses a 12-column grid.

                EXACT structure required:
                [
                  {
                    "id": "kpi_total_listings",
                    "position": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "widget": {
                      "type": "kpi",
                      "config": {"label": "Total Listings"}
                    },
                    "dataSource": {
                      "connectionId": <connection_id>,
                      "sql": "SELECT COUNT(*) AS value FROM listings",
                      "mapping": {"type": "kpi", "valueColumn": "value"}
                    }
                  },
                  {
                    "id": "chart_by_type",
                    "position": {"x": 0, "y": 5, "w": 12, "h": 5},
                    "widget": {
                      "type": "chart",
                      "config": {"type": "bar", "title": "Listings by Property Type"}
                    },
                    "dataSource": {
                      "connectionId": <connection_id>,
                      "sql": "SELECT property_type, COUNT(*) AS count FROM listings GROUP BY property_type",
                      "mapping": {
                        "type": "chart",
                        "labelColumn": "property_type",
                        "datasetColumns": [{"column": "count", "label": "Count"}]
                      }
                    }
                  },
                  {
                    "id": "table_top",
                    "position": {"x": 0, "y": 6, "w": 12, "h": 5},
                    "widget": {
                      "type": "table",
                      "config": {
                        "columns": [{"key": "address", "label": "Address"}, {"key": "price", "label": "Price", "sortable": true}]
                      }
                    },
                    "dataSource": {
                      "connectionId": <connection_id>,
                      "sql": "SELECT address, price FROM listings ORDER BY price DESC LIMIT 20",
                      "mapping": {
                        "type": "table",
                        "columnConfig": [{"column": "address", "label": "Address"}, {"column": "price", "label": "Price", "sortable": true}]
                      }
                    }
                  }
                ]

                Per-type config fields (non-data fields only — data is auto-populated from dataSource):
                - kpi: label (string, required), prefix (optional), suffix (optional)
                - chart: type ("bar"|"line"|"pie"|"doughnut"|"area"|"scatter"), title (optional),
                    options (optional): {stacked, indexAxis, showValues, showLegend, legendPosition,
                    showGrid, sortBy, sortDirection}
                - table: columns: [{key, label, sortable?}] (defines headers; rows are auto-populated)
                - text: content (markdown string), alignment (optional)
                - filter: controls: [{type, label, key, column (required), optionsSource: {connectionId, sql} for dropdown}]

                Layout guidelines (12-column grid, storytelling structure):
                  Section 1 — KPI row (y=0):
                    3 KPIs at w=4 (x=0,4,8) or 4 KPIs at w=3 (x=0,3,6,9). h=2.
                  Section 2 — Filter bar (y=2):
                    w=12, h=2. Add dropdowns for key categories, date_range for time columns.
                  Section headers (text widgets):
                    w=12, h=1. Place at y=4, y=10, or y=15 as dividers between sections.
                  Section 3 — Analysis charts (y=5 to y=14):
                    SIDE-BY-SIDE pairs: two w=6 h=5 at same y, or w=4+w=8.
                    w=12 h=6 ONLY for time-series line/area. Pie/doughnut: w=4 or w=6 only.
                    Use 2+ different chart types. Aim for 3-5 charts.
                  Section 4 — Detail table (y=16+):
                    w=12, h=5.
                  Target 9-13 widgets total (min 7, max 14).

                Mapping types:
                - chart:  { type, labelColumn, datasetColumns: [{column, label}] }
                - kpi:    { type, valueColumn, trendValueColumn? (optional), sparklineColumn? (optional) }
                - table:  { type, columnConfig: [{column, label, sortable?, format?}] }

        Returns:
            JSON with success, dashboard_id, and message
        """
        # Parse widgets JSON
        try:
            widgets = json.loads(widgets_json)
        except json.JSONDecodeError as e:
            return json.dumps({"success": False, "message": f"widgets_json is not valid JSON: {e}"})

        if not isinstance(widgets, list):
            return json.dumps({"success": False, "message": "widgets_json must be a JSON array"})

        # Validate widget structure
        error = _validate_widgets(widgets)
        if error:
            return json.dumps({"success": False, "message": f"Widget validation failed: {error}"})

        # Verify connection access for any SQL-backed widgets
        for w in widgets:
            if "dataSource" in w:
                cid = w["dataSource"]["connectionId"]
                if not context.can_access_connection(cid):
                    return json.dumps({
                        "success": False,
                        "message": f"Connection {cid} in dataSource is not accessible to you.",
                    })

        # Validate mapping columns against schema
        schema_warnings = _validate_widget_sql_schema(widgets)
        if schema_warnings:
            return json.dumps({
                "success": False,
                "message": (
                    "Widget SQL schema validation failed. Fix the SQL and retry.\n"
                    + "\n".join(f"- {w}" for w in schema_warnings)
                ),
            })

        # Auto-execute SQL for SQL-backed widgets and populate config
        for w in widgets:
            if "dataSource" in w:
                await _execute_widget_sql(w, db_session_factory)

        db = db_session_factory()
        try:
            dashboard = Dashboard(
                user_id=context.user_id,
                title=title,
                description=description or None,
                widgets=widgets,
            )
            db.add(dashboard)
            db.commit()
            db.refresh(dashboard)
            return json.dumps({
                "success": True,
                "dashboard_id": dashboard.id,
                "message": f"Dashboard '{title}' created with {len(widgets)} widget(s). Navigate to /dashboard to view it.",
            })
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create dashboard: {e}")
            return json.dumps({"success": False, "message": f"Database error: {e}"})
        finally:
            db.close()

    return [create_dashboard]


def build_create_dashboard_tool(context: AgentContext) -> List:
    """Registry-compatible wrapper: imports SessionLocal and delegates to build_dashboard_tools."""
    from backend.database.session import SessionLocal
    return build_dashboard_tools(context, SessionLocal)
