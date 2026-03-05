"""
Dashboard Tools — LangChain tool builders for dashboard creation.

Kept as a standalone module to avoid circular imports between graph.py and tool_registry.py.
"""
from typing import List, Callable
from backend.agents.context import AgentContext
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


def _execute_widget_sql(widget: dict, db_session_factory: Callable) -> None:
    """
    Execute the dataSource SQL for a widget and merge results into widget.widget.config.

    Modifies widget in-place. Errors are logged but not raised — the widget is left
    with whatever config was provided by the LLM if execution fails.
    """
    from backend.connectors.factory import get_connector
    from backend.models.database_connection import DatabaseConnection
    from backend.services.widget_transform import transform_widget_data

    data_source = widget.get("dataSource")
    if not data_source:
        return

    connection_id = data_source.get("connectionId")
    sql = data_source.get("sql")
    mapping = data_source.get("mapping")

    db = db_session_factory()
    connector = None
    try:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
        ).first()
        if not connection:
            logger.warning(f"Widget '{widget.get('id')}': connection {connection_id} not found, skipping SQL execution")
            return

        connector = get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password,
            ssl_enabled=connection.ssl_enabled,
            ssl_ca_cert=connection.ssl_ca_cert,
        )

        result = connector.execute_query(sql)
        config = transform_widget_data(result, mapping)
        widget["widget"]["config"].update(config)
        logger.info(f"Widget '{widget.get('id')}': SQL executed, config populated with {result.row_count} rows")
    except Exception as e:
        logger.warning(f"Widget '{widget.get('id')}': SQL execution failed, using LLM-provided config: {e}")
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
                - chart: type ("bar"|"line"|"pie"|"doughnut"|"area"), title (optional)
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

        # Auto-execute SQL for SQL-backed widgets and populate config
        for w in widgets:
            if "dataSource" in w:
                _execute_widget_sql(w, db_session_factory)

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
