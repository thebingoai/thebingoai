"""
Dashboard Tools — LangChain tool builders for dashboard creation.

Kept as a standalone module to avoid circular imports between graph.py and tool_registry.py.
"""
from typing import List, Callable
from backend.agents.context import AgentContext
from backend.connectors.factory import get_connector_for_connection, get_connector_registration
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
    from backend.agents.sql_validation import (
        extract_table_refs, extract_cte_names, get_all_tables,
        validate_tables, validate_sql_columns, validate_mapping_columns,
    )

    # Collect unique connection IDs and load schemas
    connection_ids = {
        w["dataSource"]["connectionId"]
        for w in widgets
        if "dataSource" in w
    }
    schemas: dict[int, dict] = {}
    for cid in connection_ids:
        try:
            schemas[cid] = load_schema_file(cid)
        except FileNotFoundError:
            pass  # Schema not cached — skip validation for this connection

    if not schemas:
        return []

    warnings: list[str] = []
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

        table_matches, table_aliases = extract_table_refs(sql)
        if not table_matches:
            continue

        cte_names = extract_cte_names(sql)
        known_virtual = cte_names | table_aliases
        all_schema_tables = get_all_tables(schema_json)
        referenced_table = table_matches[0].split(".")[-1]

        # Validate tables
        table_warnings = validate_tables(table_matches, known_virtual, all_schema_tables, widget_id)
        if table_warnings:
            warnings.extend(table_warnings)
            continue

        # Validate SQL columns
        col_warnings = validate_sql_columns(
            sql, schema_json, table_matches, table_aliases, all_schema_tables, widget_id,
        )
        if col_warnings:
            warnings.extend(col_warnings)
            continue  # Skip mapping validation — fix SQL first

        # Validate mapping columns
        mapping_warnings = validate_mapping_columns(
            sql, mapping, mapping.get("type", ""), schema_json,
            table_matches, referenced_table, widget_id,
        )
        warnings.extend(mapping_warnings)

    return warnings


async def _attempt_sql_fix(
    sql: str,
    error_message: str,
    connection,
    mapping: dict,
    widget_id: str,
    widget_title: str | None = None,
    data_context: dict | None = None,
    sample_data: str = "",
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

    reg = get_connector_registration(connection.db_type)
    db_type_display = reg.sql_dialect_hint if reg and reg.sql_dialect_hint else str(connection.db_type)

    prompt = f"""You are a SQL expert. Fix the SQL query that produced an error.

Original SQL:
```sql
{sql}
```

Error:
{error_message}

Widget type: {mapping_type}
Expected output columns: {mapping_info}
Database type: {db_type_display}{title_context}
IMPORTANT: Only use table and column names that exist in the schema below. Do NOT invent table or column names.
"""

    if title_context:
        prompt += """
SEMANTIC CHECK: The fixed SQL must correctly query data that matches the widget title.
For example, if the title says "Average Price", the SQL must query a price-related column — not floor_area, size, or other unrelated columns.
"""

    if schema_summary:
        prompt += f"\nDatabase schema:\n{schema_summary}\n"

    if data_context and data_context.get("baseJoin"):
        prompt += f"\nBase join context:\n{json.dumps(data_context['baseJoin'], indent=2)}\n"

    if sample_data:
        prompt += f"\nSample data from referenced tables:\n{sample_data}\n"

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


async def _execute_widget_sql(widget: dict, db_session_factory: Callable, data_context: dict | None = None) -> str | None:
    """
    Execute the dataSource SQL for a widget and merge results into widget.widget.config.

    Modifies widget in-place. On first failure, attempts an LLM-powered SQL fix and retries once,
    including sample data and baseJoin context for better fix quality.
    Returns error string if both attempts fail, None on success.
    """
    from backend.models.database_connection import DatabaseConnection
    from backend.services.widget_transform import transform_widget_data

    data_source = widget.get("dataSource")
    if not data_source:
        return

    connection_id = data_source.get("connectionId")
    sql = data_source.get("sql")
    mapping = data_source.get("mapping")
    # Inject chartType so scatter charts produce {x,y} points
    chart_type = widget.get("widget", {}).get("config", {}).get("type")
    if chart_type and mapping and "chartType" not in mapping:
        mapping = {**mapping, "chartType": chart_type}
        data_source["mapping"] = mapping
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

        # Gather sample data from referenced tables for better fix context
        sample_data = ""
        try:
            from backend.services.schema_utils import extract_table_names
            tables = extract_table_names(sql)
            for tbl in list(tables)[:2]:
                try:
                    sample_result = connector.execute_query(f'SELECT * FROM "{tbl}" LIMIT 3')
                    sample_data += f"\nTable '{tbl}' sample:\n"
                    sample_data += f"  Columns: {sample_result.columns}\n"
                    for srow in sample_result.rows[:3]:
                        sample_data += f"  {list(srow)}\n"
                except Exception:
                    pass
        except Exception:
            pass

        # Attempt LLM-powered SQL fix with sample data + baseJoin context
        fixed_sql = await _attempt_sql_fix(
            sql=sql,
            error_message=first_error_msg,
            connection=connection,
            mapping=mapping,
            widget_id=widget_id,
            widget_title=widget_title,
            data_context=data_context,
            sample_data=sample_data,
        )

        if not fixed_sql:
            logger.warning(f"Widget '{widget_id}': LLM fix returned no SQL, using LLM-provided config")
            return first_error_msg

        logger.info(f"Widget '{widget_id}': SQL fix attempted, retrying with corrected SQL")
        try:
            result = connector.execute_query(fixed_sql)
            config = transform_widget_data(result, mapping)
            widget["widget"]["config"].update(config)
            # Persist the fixed SQL back to the widget's dataSource
            data_source["sql"] = fixed_sql
            logger.info(f"Widget '{widget_id}': SQL fix succeeded, config populated with {result.row_count} rows")
            return None
        except Exception as retry_error:
            error_msg = f"Original: {first_error_msg} | Retry: {retry_error}"
            logger.warning(f"Widget '{widget_id}': SQL fix also failed, using LLM-provided config. {error_msg}")
            return error_msg
    finally:
        if connector:
            connector.close()
        db.close()


def build_dashboard_tools(context: AgentContext, db_session_factory: Callable) -> List:
    """Return [create_dashboard, update_dashboard] tools bound to context and db_session_factory."""
    if db_session_factory is None:
        return []

    from langchain_core.tools import tool
    from backend.models.dashboard import Dashboard

    @tool
    async def create_dashboard(title: str, description: str, widgets_json: str, data_context_json: str = "") -> str:
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
                - kpi:    { type, valueColumn, trendValueColumn? (optional), sparklineXColumn? (optional), sparklineYColumn? (optional) }
                - table:  { type, columnConfig: [{column, label, sortable?, format?}] }

            data_context_json: Optional JSON string from build_dashboard_context. If provided,
                stored on the dashboard for dimension-aware filtering.

        Returns:
            JSON with success, dashboard_id, and message
        """
        # Parse data context (optional)
        data_context = None
        if data_context_json and data_context_json.strip():
            try:
                data_context = json.loads(data_context_json)
            except json.JSONDecodeError:
                logger.warning("create_dashboard: data_context_json is not valid JSON, ignoring")

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

        # Guard: reject dataset connections when CSV connector plugin is not loaded
        from backend.agents.tool_registry import get_plugin_tool_builders
        plugin_builders = get_plugin_tool_builders()
        csv_plugin_loaded = "create_dataset_from_upload" in plugin_builders
        if not csv_plugin_loaded:
            from backend.models.database_connection import DatabaseConnection as _DC
            _guard_db = db_session_factory()
            try:
                ds_cids = {w["dataSource"]["connectionId"] for w in widgets if "dataSource" in w}
                for cid in ds_cids:
                    conn = _guard_db.query(_DC).filter(_DC.id == cid).first()
                    if conn and conn.db_type == "dataset":
                        return json.dumps({
                            "success": False,
                            "message": (
                                f"Connection {cid} is a dataset connection. "
                                "Dataset dashboards require the CSV connector enterprise plugin."
                            ),
                        })
            except Exception:
                pass  # Guard is best-effort; don't block on DB errors
            finally:
                _guard_db.close()

        # Validate mapping columns against schema (warnings only — SQL execution is the real test)
        schema_warnings = _validate_widget_sql_schema(widgets)
        if schema_warnings:
            logger.warning("Schema validation warnings for '%s': %s", title, "; ".join(schema_warnings))

        # Auto-execute SQL for SQL-backed widgets and populate config
        for w in widgets:
            if "dataSource" in w:
                await _execute_widget_sql(w, db_session_factory, data_context=data_context)

        db = db_session_factory()
        try:
            dashboard = Dashboard(
                user_id=context.user_id,
                title=title,
                description=description or None,
                widgets=widgets,
                data_context=data_context,
            )
            db.add(dashboard)
            db.commit()
            db.refresh(dashboard)

            # Dispatch async cache materialization (non-blocking)
            try:
                from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
                execute_dashboard_refresh.delay(dashboard.id)
                logger.info(f"Dispatched materialization task for new dashboard {dashboard.id}")
            except Exception as mat_err:
                logger.warning(f"Failed to dispatch materialization for dashboard {dashboard.id}: {mat_err}")

            response = {
                "success": True,
                "dashboard_id": dashboard.id,
                "message": f"Dashboard '{title}' created with {len(widgets)} widget(s). Navigate to /dashboard to view it.",
            }
            if schema_warnings:
                response["warnings"] = schema_warnings
                response["message"] += (
                    f"\n\nNote: {len(schema_warnings)} widget(s) had SQL column warnings — "
                    "their data may be incomplete. Fix the SQL for these widgets and call "
                    "update_dashboard to update them."
                )
            return json.dumps(response)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create dashboard: {e}")
            return json.dumps({"success": False, "message": f"Database error: {e}"})
        finally:
            db.close()

    @tool
    async def update_dashboard(dashboard_id: int, widgets: list, title: str = "", description: str = "", data_context_json: str = "") -> str:
        """
        Update an existing dashboard's widgets, title, and/or description.

        Use this tool instead of create_dashboard when modifying an existing dashboard.
        The widgets list must contain the COMPLETE updated widget array (not just changes).
        For SQL-backed widgets, SQL is auto-executed just like create_dashboard.

        Args:
            dashboard_id: ID of the dashboard to update (get from list_dashboards)
            widgets: List of widget objects. Same format as create_dashboard — every widget
                needs id, position, widget.type, widget.config, and optionally dataSource
                with connectionId, sql, and mapping.
            title: New dashboard title (empty string keeps the existing title)
            description: New dashboard description (empty string keeps the existing description)

        Returns:
            JSON with success, dashboard_id, and message
        """
        logger.info(f"update_dashboard called: dashboard_id={dashboard_id}, widget_count={len(widgets)}")

        # Parse data context (optional)
        data_context = None
        if data_context_json and data_context_json.strip():
            try:
                data_context = json.loads(data_context_json)
            except json.JSONDecodeError:
                logger.warning("update_dashboard: data_context_json is not valid JSON, ignoring")

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

        # Validate mapping columns against schema (warnings only — SQL execution is the real test)
        schema_warnings = _validate_widget_sql_schema(widgets)
        if schema_warnings:
            logger.warning("Schema validation warnings for dashboard %d: %s", dashboard_id, "; ".join(schema_warnings))

        # Load existing dashboard to compare SQL and carry over unchanged widget data
        db = db_session_factory()
        try:
            dashboard = db.query(Dashboard).filter(
                Dashboard.id == dashboard_id,
                Dashboard.user_id == context.user_id,
            ).first()
            if not dashboard:
                return json.dumps({"success": False, "message": f"Dashboard {dashboard_id} not found or not accessible."})

            # Build map of existing widget SQL and config for comparison
            existing_widgets_map = {}
            for ew in (dashboard.widgets or []):
                existing_widgets_map[ew.get("id")] = ew
        finally:
            db.close()

        # Only execute SQL for widgets whose SQL changed or that are new
        sql_changed = False
        for w in widgets:
            if "dataSource" not in w:
                continue
            new_sql = w["dataSource"].get("sql")
            new_conn = w["dataSource"].get("connectionId")
            existing_w = existing_widgets_map.get(w.get("id"))
            old_sql = existing_w.get("dataSource", {}).get("sql") if existing_w else None
            old_conn = existing_w.get("dataSource", {}).get("connectionId") if existing_w else None

            if old_sql == new_sql and old_sql is not None and old_conn == new_conn:
                # SQL unchanged — carry over existing computed data instead of re-executing
                existing_config = existing_w.get("widget", {}).get("config", {})
                w_config = w.get("widget", {}).get("config", {})
                for key in ("data", "rows", "value"):
                    if key in existing_config:
                        w_config[key] = existing_config[key]
                logger.info(f"Skipping SQL execution for unchanged widget '{w.get('id')}'")
            else:
                sql_changed = True
                await _execute_widget_sql(w, db_session_factory, data_context=data_context)

        db = db_session_factory()
        try:
            dashboard = db.query(Dashboard).filter(
                Dashboard.id == dashboard_id,
                Dashboard.user_id == context.user_id,
            ).first()
            if not dashboard:
                return json.dumps({"success": False, "message": f"Dashboard {dashboard_id} not found or not accessible."})

            from sqlalchemy.orm.attributes import flag_modified

            if title:
                dashboard.title = title
            if description:
                dashboard.description = description
            dashboard.widgets = widgets
            flag_modified(dashboard, "widgets")
            if data_context is not None:
                dashboard.data_context = data_context
                flag_modified(dashboard, "data_context")

            db.commit()
            db.refresh(dashboard)

            # Dispatch async cache materialization only if SQL/connections changed
            if sql_changed:
                try:
                    from backend.tasks.dashboard_refresh_tasks import execute_dashboard_refresh
                    execute_dashboard_refresh.delay(dashboard.id)
                    logger.info(f"Dispatched materialization task for updated dashboard {dashboard.id}")
                except Exception as mat_err:
                    logger.warning(f"Failed to dispatch materialization for dashboard {dashboard.id}: {mat_err}")

            response = {
                "success": True,
                "dashboard_id": dashboard.id,
                "message": f"Dashboard '{dashboard.title}' updated with {len(widgets)} widget(s). Navigate to /dashboard to view it.",
            }
            if schema_warnings:
                response["warnings"] = schema_warnings
                response["message"] += (
                    f"\n\nNote: {len(schema_warnings)} widget(s) had SQL column warnings — "
                    "their data may be incomplete."
                )
            return json.dumps(response)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update dashboard: {e}")
            return json.dumps({"success": False, "message": f"Database error: {e}"})
        finally:
            db.close()

    return [create_dashboard, update_dashboard]


def build_create_dashboard_tool(context: AgentContext) -> List:
    """Registry-compatible wrapper: imports SessionLocal and delegates to build_dashboard_tools."""
    from backend.database.session import SessionLocal
    return build_dashboard_tools(context, SessionLocal)
