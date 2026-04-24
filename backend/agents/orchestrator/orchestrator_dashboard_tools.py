from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.agents.dashboard_agent import invoke_dashboard_agent
from typing import List, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)



async def _do_create_dashboard(
    context: AgentContext,
    db_session_factory: Callable,
    request: str,
    target_connection_id: int | None = None,
) -> str:
    """Business logic for create_dashboard tool."""
    from backend.models.database_connection import DatabaseConnection
    from backend.config import settings as _settings

    db = db_session_factory()
    try:
        fresh_ids = [
            row.id for row in db.query(DatabaseConnection.id)
            .filter(DatabaseConnection.user_id == context.user_id)
            .all()
        ]
    finally:
        db.close()
    context.available_connections = fresh_ids

    # If mesh is enabled, dispatch via message bus to dashboard agent peer
    if _settings.agent_mesh_enabled and context.session_id:
        from backend.services.agent_registry import AgentRegistry
        from backend.services.agent_discovery import AgentDiscovery
        from backend.services.agent_message_bus import AgentMessageBus

        registry = AgentRegistry()
        discovery = AgentDiscovery(redis_client=registry.redis)
        dash_session = discovery.find_session_by_type(context.user_id, "dashboard_agent")

        if dash_session:
            db2 = db_session_factory()
            try:
                bus = AgentMessageBus(db_session=db2, redis_client=registry.redis)
                response = bus.send_and_wait(
                    user_id=context.user_id,
                    from_session_id=context.session_id,
                    to_session_id=dash_session["session_id"],
                    content={"text": request, "available_connections": fresh_ids},
                    timeout=120,
                )
                if response:
                    return json.dumps(response)
                return json.dumps({"success": False, "message": "Dashboard agent did not respond in time"})
            finally:
                db2.close()

    # Auto-promote ephemeral dataset when used for a dashboard
    if target_connection_id:
        from backend.models.database_connection import DatabaseConnection as _DC
        _db = db_session_factory()
        try:
            _conn = _db.query(_DC).filter(
                _DC.id == target_connection_id,
                _DC.user_id == context.user_id,
                _DC.db_type == "dataset",
                _DC.is_ephemeral == True,  # noqa: E712
            ).first()
            if _conn:
                _conn.is_ephemeral = False
                _db.commit()
                logger.info("Promoted ephemeral dataset %s for dashboard creation", target_connection_id)
        finally:
            _db.close()

    result = await invoke_dashboard_agent(request, context, db_session_factory, target_connection_id=target_connection_id)
    return json.dumps(result)


async def _do_update_dashboard(
    context: AgentContext,
    db_session_factory: Callable,
    request: str,
    dashboard_id: int,
) -> str:
    """Business logic for update_dashboard tool."""
    from backend.models.database_connection import DatabaseConnection
    from backend.models.dashboard import Dashboard

    # Refresh available connections and load existing dashboard in one session
    db = db_session_factory()
    try:
        fresh_ids = [
            row.id for row in db.query(DatabaseConnection.id)
            .filter(DatabaseConnection.user_id == context.user_id)
            .all()
        ]
        context.available_connections = fresh_ids

        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == context.user_id,
        ).first()
        if not dashboard:
            return json.dumps({"success": False, "message": f"Dashboard {dashboard_id} not found or not accessible."})

        current_title = dashboard.title
        current_description = dashboard.description
        current_widgets = dashboard.widgets or []
    finally:
        db.close()

    # Extract target connection from existing widgets
    target_connection_id = None
    for w in current_widgets:
        ds = w.get("dataSource")
        if ds and ds.get("connectionId"):
            target_connection_id = ds["connectionId"]
            break

    # Strip auto-populated data from widgets to keep the prompt compact.
    # These fields are re-populated by _execute_widget_sql at save time.
    import copy
    stripped_widgets = copy.deepcopy(current_widgets)
    for w in stripped_widgets:
        config = w.get("widget", {}).get("config", {})
        config.pop("data", None)     # chart data (labels + datasets)
        config.pop("rows", None)     # table row data
        config.pop("value", None)    # KPI computed value

    # Build enriched request with existing dashboard context
    enriched_request = (
        f"UPDATE existing dashboard (id={dashboard_id}).\n"
        f"Current title: {current_title}\n"
        f"Current description: {current_description}\n"
        f"Current widgets ({len(current_widgets)} total):\n"
        f"{json.dumps(stripped_widgets, indent=2)}\n\n"
        f"User's edit request: {request}\n\n"
        f"IMPORTANT: Use the update_dashboard tool (NOT create_dashboard) to save changes. "
        f"Pass dashboard_id={dashboard_id}."
    )

    result = await invoke_dashboard_agent(enriched_request, context, db_session_factory, target_connection_id=target_connection_id)
    return json.dumps(result)


def _do_list_dashboards(
    context: AgentContext,
    db_session_factory: Callable,
) -> str:
    """Business logic for list_dashboards tool."""
    from backend.models.dashboard import Dashboard

    db = db_session_factory()
    try:
        dashboards = (
            db.query(Dashboard)
            .filter(Dashboard.user_id == context.user_id)
            .all()
        )
        items = []
        for d in dashboards:
            items.append({
                "id": d.id,
                "title": d.title,
                "description": d.description,
                "created_at": str(d.created_at),
                "widget_count": len(d.widgets) if d.widgets else 0,
            })
        return json.dumps({"total": len(items), "dashboards": items})
    finally:
        db.close()


def _do_list_connections(
    context: AgentContext,
    db_session_factory: Callable,
) -> str:
    """Business logic for list_connections tool."""
    from backend.models.database_connection import DatabaseConnection

    db = db_session_factory()
    try:
        connections = (
            db.query(DatabaseConnection)
            .filter(DatabaseConnection.user_id == context.user_id)
            .all()
        )
        items = []
        for c in connections:
            items.append({
                "id": c.id,
                "name": c.name,
                "db_type": c.db_type if c.db_type else None,
                "database": c.database,
            })
        return json.dumps({"total": len(items), "connections": items})
    finally:
        db.close()


async def _do_read_dashboard(
    context: AgentContext,
    db_session_factory: Callable,
    dashboard_id: int,
    widget_id: str = "",
) -> str:
    """Business logic for read_dashboard tool."""
    from backend.models.dashboard import Dashboard
    from backend.agents.dashboard_tools import _execute_widget_sql
    import copy

    db = db_session_factory()
    try:
        dashboard = db.query(Dashboard).filter(
            Dashboard.id == dashboard_id,
            Dashboard.user_id == context.user_id,
        ).first()
        if not dashboard:
            return json.dumps({"success": False, "message": f"Dashboard {dashboard_id} not found or not accessible."})

        title = dashboard.title
        description = dashboard.description
        widgets = copy.deepcopy(dashboard.widgets or [])
    finally:
        db.close()

    # Filter to specific widget if requested
    if widget_id:
        widgets = [w for w in widgets if w.get("id") == widget_id]
        if not widgets:
            # Try matching by title/label in config
            all_widgets = copy.deepcopy(dashboard.widgets or []) if not widgets else widgets
            db2 = db_session_factory()
            try:
                dashboard2 = db2.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
                all_widgets = copy.deepcopy(dashboard2.widgets or []) if dashboard2 else []
            finally:
                db2.close()
            for w in all_widgets:
                config = w.get("widget", {}).get("config", {})
                w_title = config.get("title", "") or config.get("label", "") or ""
                if widget_id.lower() in w_title.lower():
                    widgets = [w]
                    break
            if not widgets:
                return json.dumps({"success": False, "message": f"Widget '{widget_id}' not found in dashboard {dashboard_id}."})

    # Re-execute SQL only for the widgets we need
    for w in widgets:
        if "dataSource" in w:
            await _execute_widget_sql(w, db_session_factory)

    # Build a concise summary for the LLM
    widget_summaries = []
    for w in widgets:
        wtype = w.get("widget", {}).get("type", "unknown")
        config = w.get("widget", {}).get("config", {})
        summary = {
            "id": w.get("id"),
            "type": wtype,
            "position": w.get("position"),
        }

        if wtype == "kpi":
            summary["label"] = config.get("label")
            summary["value"] = config.get("value")
            summary["prefix"] = config.get("prefix")
            summary["suffix"] = config.get("suffix")
            if config.get("trend"):
                summary["trend"] = config["trend"]
        elif wtype == "chart":
            summary["chart_type"] = config.get("type")
            summary["title"] = config.get("title")
            summary["data"] = config.get("data")
        elif wtype == "table":
            summary["title"] = config.get("title")
            summary["columns"] = config.get("columns")
            summary["rows"] = config.get("rows")
        elif wtype == "text":
            summary["content"] = config.get("content")
        elif wtype == "filter":
            summary["controls"] = config.get("controls")

        widget_summaries.append(summary)

    return json.dumps({
        "success": True,
        "dashboard_id": dashboard_id,
        "title": title,
        "description": description,
        "widget_count": len(widget_summaries),
        "widgets": widget_summaries,
    })


def build_dashboard_tools(context: AgentContext, db_session_factory: Optional[Callable] = None) -> List:
    """Return dashboard tools when db_session_factory is available."""
    if db_session_factory is None:
        return []

    @tool
    async def create_dashboard(request: str, target_connection_id: int | None = None) -> str:
        """
        Create a persistent, fully-featured dashboard from a natural language request.

        IMPORTANT: If the user wants a dashboard from an uploaded file, you MUST call
        create_dataset_from_upload FIRST and wait for its result (which contains the
        connection_id), THEN call this tool with target_connection_id set to that
        connection_id. Do NOT call both tools simultaneously.

        This tool delegates to a specialized dashboard sub-agent that handles the entire
        dashboard creation workflow autonomously, end-to-end:

        1. **Schema exploration**: Connects to the user's database(s) and discovers available
           tables, columns, data types, and relationships — no prior knowledge of the schema
           is required.

        2. **SQL generation**: Designs and validates SQL queries tailored to the user's request,
           adapting to the actual structure of the data found during schema exploration.

        3. **Widget creation**: Produces a variety of visual widget types based on what best
           suits the underlying data:
              - KPI cards (single-value metrics, e.g. total revenue, active users)
              - Bar charts (comparisons across categories)
              - Line charts (trends over time)
              - Tables (detailed row-level data or multi-column summaries)

        4. **Dashboard assembly**: Arranges widgets into a coherent layout and persists the
           dashboard so the user can view and interact with it immediately.

        Use this tool ONLY for creating NEW dashboards from scratch. Do NOT use this tool if
        the user wants to edit, modify, update, or add to an EXISTING dashboard — use
        update_dashboard instead. The sub-agent will autonomously determine what data is
        available and what visualisations are appropriate.

        Args:
            request: Natural language description of the dashboard to create. Can be as
                     high-level as "create a sales dashboard" or as specific as "build a
                     dashboard showing monthly revenue by region and top 10 customers".

        Returns:
            JSON string with the following fields:
                - success (bool): Whether the dashboard was created successfully
                - dashboard_id (str): Unique identifier of the created dashboard
                - message (str): Human-readable summary of what was created
                - steps (list): Ordered list of actions taken by the sub-agent
        """
        return await _do_create_dashboard(context, db_session_factory, request, target_connection_id)

    @tool
    async def update_dashboard(request: str, dashboard_id: int) -> str:
        """
        Edit or modify an existing dashboard based on a natural language request.

        Use this tool when the user wants to change, update, add to, or remove from
        an existing dashboard. Call list_dashboards first to find the dashboard_id
        if the user refers to a dashboard by name.

        IMPORTANT: Do NOT use create_dashboard for edit requests — that creates a
        duplicate. Always use this tool for modifications to existing dashboards.

        Args:
            request: Natural language description of what to change (e.g.,
                     "add a total revenue KPI", "remove the table widget",
                     "change the bar chart to a line chart")
            dashboard_id: ID of the dashboard to update (from list_dashboards)

        Returns:
            JSON string with success, dashboard_id, message, and steps
        """
        return await _do_update_dashboard(context, db_session_factory, request, dashboard_id)

    @tool
    def list_dashboards() -> str:
        """
        List all dashboards owned by the current user.

        Use this tool when the user asks about their dashboards — for example
        "how many dashboards do I have?", "show me my dashboards", or
        "what dashboards exist?".

        Returns:
            JSON with total count and a list of dashboards (id, title,
            description, created_at, widget_count).
        """
        return _do_list_dashboards(context, db_session_factory)

    @tool
    def list_connections() -> str:
        """
        List all database connections available to the current user.

        Use this tool when the user asks about their data connections — for
        example "what databases do I have connected?", "show my connections",
        or "how many data sources are there?".

        Returns:
            JSON with total count and a list of connections (id, name,
            db_type, database).
        """
        return _do_list_connections(context, db_session_factory)

    @tool
    async def read_dashboard(dashboard_id: int, widget_id: str = "") -> str:
        """
        Read a dashboard's content including live widget data.

        Use this tool when the user asks about what a specific dashboard shows,
        wants to know current values or metrics, or asks to check/inspect/verify
        a widget (e.g. "what's the total revenue?", "check the line chart",
        "what does my sales dashboard show?").

        This is a READ-ONLY tool — it never modifies the dashboard.

        Call list_dashboards first if you need to find the dashboard_id.

        Args:
            dashboard_id: ID of the dashboard to read (from list_dashboards)
            widget_id: Optional widget ID to read only that specific widget.
                       Leave empty to read all widgets. Use this when the user
                       asks about a specific chart, KPI, or table by name.

        Returns:
            JSON with dashboard title, description, and widget data.
        """
        return await _do_read_dashboard(context, db_session_factory, dashboard_id, widget_id)

    tools = [create_dashboard, update_dashboard, read_dashboard, list_dashboards, list_connections]

    # Dynamically include plugin-provided tools
    from backend.agents.tool_registry import get_plugin_tool_builders
    plugin_builders = get_plugin_tool_builders()
    if "create_dataset_from_upload" in plugin_builders:
        tools.extend(plugin_builders["create_dataset_from_upload"](context, db_session_factory))

    return tools
