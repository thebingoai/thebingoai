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

        Call this after gathering data with data_agent to confirm what metrics are available.
        Build the widgets based on real query results — don't invent values.

        Args:
            title: Dashboard title (e.g. "Property Overview Dashboard")
            description: Brief description of what the dashboard shows
            widgets_json: JSON array of widget objects. CRITICAL: each widget.widget must have
                a nested "config" sub-object containing the display data. Layout uses a 12-column grid.

                EXACT structure required:
                [
                  {
                    "id": "kpi_total_listings",
                    "position": {"x": 0, "y": 0, "w": 3, "h": 2},
                    "widget": {
                      "type": "kpi",
                      "config": {
                        "label": "Total Listings",
                        "value": 38121,
                        "suffix": "properties"
                      }
                    }
                  },
                  {
                    "id": "chart_by_type",
                    "position": {"x": 0, "y": 2, "w": 12, "h": 4},
                    "widget": {
                      "type": "chart",
                      "config": {
                        "type": "bar",
                        "title": "Listings by Property Type",
                        "data": {
                          "labels": ["Condominium", "Apartment"],
                          "datasets": [{"label": "Count", "data": [6870, 1933]}]
                        }
                      }
                    }
                  },
                  {
                    "id": "table_top",
                    "position": {"x": 0, "y": 6, "w": 12, "h": 5},
                    "widget": {
                      "type": "table",
                      "config": {
                        "columns": [{"key": "address", "label": "Address"}, {"key": "price", "label": "Price", "sortable": true}],
                        "rows": [{"address": "...", "price": 450000}]
                      }
                    }
                  }
                ]

                Per-type config fields:
                - kpi: label (string, required), value (number|string, required), prefix (optional), suffix (optional),
                       trend: {direction: "up"|"down"|"neutral", value: number, period: string} (optional)
                - chart: type ("bar"|"line"|"pie"|"doughnut"|"area"), title (optional),
                         data: {labels: [...], datasets: [{label, data: [...]}]}
                - table: columns: [{key, label, sortable?}], rows: [{key: value, ...}]
                - text: content (markdown string), alignment (optional)
                - filter: controls: [{type, label, key}]

                Layout guidelines (12-column grid):
                  KPI cards:    w=3, h=2, y=0  (place up to 4 at x=0,3,6,9)
                  Half charts:  w=6, h=4, y=2
                  Full charts:  w=12, h=4, y=2
                  Tables:       w=12, h=5, y=6

                SQL-backed widgets (RECOMMENDED for chart/kpi/table):
                Add an optional "dataSource" field so data can be refreshed live:
                {
                  "id": "chart_sales",
                  "position": {"x": 0, "y": 2, "w": 12, "h": 4},
                  "widget": {
                    "type": "chart",
                    "config": {
                      "type": "bar",
                      "title": "Sales by City",
                      "data": {"labels": ["NY", "LA"], "datasets": [{"label": "Sales", "data": [500, 300]}]}
                    }
                  },
                  "dataSource": {
                    "connectionId": <connection_id>,
                    "sql": "SELECT city, SUM(amount) as sales FROM orders GROUP BY city",
                    "mapping": {
                      "type": "chart",
                      "labelColumn": "city",
                      "datasetColumns": [{"column": "sales", "label": "Sales"}]
                    }
                  }
                }

                Mapping types:
                - chart:  { type, labelColumn, datasetColumns: [{column, label}] }
                - kpi:    { type, valueColumn, trendValueColumn? (optional), sparklineColumn? (optional) }
                - table:  { type, columnConfig: [{column, label, sortable?, format?}] }

                IMPORTANT: Always populate widget.config with real query data for immediate display.
                The dataSource enables refresh later — it does NOT replace config.

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
