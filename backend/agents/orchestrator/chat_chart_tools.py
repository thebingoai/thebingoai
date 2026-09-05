"""Chat chart tools — render a chart inline in a chat reply.

Two tools:
  - generate_chat_chart: ad-hoc question -> one frozen chart snapshot, no
    Dashboard row. Reuses the dashboard_agent widget hydration + SQL exec
    pipeline (build_widgets, _execute_widget_sql) so chart-type rules and SQL
    generation stay identical to real dashboards.
  - select_dashboard_widget: @mentioned dashboard -> pick the one existing
    widget that best matches the question, rendered live (real widget, not a
    snapshot).

Row data never reaches the LLM: generate_chat_chart stores the hydrated
widget (config + data) server-side via query_result_store and returns only a
lean confirmation + opaque chart_ref. The orchestrator resolves chart_ref to
the full widget after the LLM turn ends (see resolve_chart_specs_from_tool_results
below), mirroring how execute_query already keeps row data out of LLM context.
The SQL-repair path is covered too: this tool passes allow_row_sampling=False,
so the repair prompt _execute_widget_sql builds carries schema + error only,
never sampled rows (dashboards still sample unless metadata_only_llm is on).
"""
from __future__ import annotations

import copy
import json
import logging
import uuid
from typing import Any, Callable, Optional

from langchain_core.tools import tool

from backend.agents.context import AgentContext
from backend.services.query_result_store import store_query_result, get_query_result

logger = logging.getLogger(__name__)

_CHART_TOOL_NAMES = ("generate_chat_chart", "select_dashboard_widget")


def build_chat_chart_tools(context: AgentContext, db_session_factory: Callable) -> list:
    """Return [generate_chat_chart, select_dashboard_widget] bound to context."""
    if db_session_factory is None:
        return []

    @tool
    async def generate_chat_chart(widget: dict) -> str:
        """
        Render ONE chart inline in this chat reply, for an ad-hoc question
        ("show sales by region", "what's our monthly signup trend"). The chart
        is a frozen snapshot — NOT saved to a dashboard. Do NOT use this to
        build or update a real dashboard; use create_dashboard/update_dashboard
        for that. Call at most once per turn.

        Args:
            widget: LEAN widget object, same shape as one entry in
                create_dashboard's `widgets` list. Required: "type" (use
                "chart" or "kpi"), "connectionId", "sql".
                For type="chart" also provide: "chartType"
                (bar|line|pie|doughnut|area|scatter|bubble|funnel|timeline).

                Category charts (bar|line|pie|doughnut|area|funnel): provide
                "labelColumn" (the dimension) and "datasetColumns" (list of
                {column, label, aggregation?} for the metric(s) — do NOT
                repeat labelColumn inside datasetColumns). Category charts
                MUST aggregate — GROUP BY in the SQL, or set "aggregation" on
                each datasetColumns entry. "aggregation" values are lowercase:
                sum|avg|count|countDistinct|min|max|first|last ("SUM" is NOT
                recognised).

                Breakdown / "stack by" / "split by" a second dimension: set
                "breakdownColumn" to that column — it splits the FIRST metric
                into one series per distinct value. A second dimension in the
                SQL does NOTHING on its own; without breakdownColumn every
                category collapses into a single series. Add
                "options": {"stacked": "standard"} for a stacked chart, or
                "percentage" for 100%-stacked; omit for grouped bars / multi
                line. (sliceLabel is a pie-only label option — it is NOT a
                breakdown.)
                Example: {"type": "chart", "chartType": "bar",
                "connectionId": 8, "sql": "SELECT quarter, category, revenue
                FROM sales", "labelColumn": "quarter",
                "breakdownColumn": "category", "datasetColumns": [{"column":
                "revenue", "label": "Revenue", "aggregation": "sum"}],
                "options": {"stacked": "standard"}}

                Time buckets: set "dateGranularity" (year|quarter|month|week|
                day|hour, or hour_of_day|day_of_week|month_of_year for
                seasonality) to bucket a timestamp labelColumn — the backend
                buckets and aggregates in Python, so the SQL can return raw
                timestamp/category/metric rows with no DATE_TRUNC and no pivot.

                Scatter/bubble charts (point-based, NOT labelColumn/
                datasetColumns): provide "xMetricColumn" and "yMetricColumn"
                (the two metric columns from the SQL), optionally
                "xAggregation"/"yAggregation" (same lowercase enum) to collapse
                repeated x values. Bubble additionally requires
                "sizeMetricColumn". Optional "labelColumn" groups points into
                one series per distinct value.
                Example: {"type": "chart", "chartType": "bubble",
                "connectionId": 8, "sql": "SELECT price, minimum_nights,
                number_of_reviews FROM listings",
                "xMetricColumn": "price", "yMetricColumn": "minimum_nights",
                "sizeMetricColumn": "number_of_reviews"}

                Timeline charts (events/phases with a start AND end date —
                NOT a simple time series; use line/area with a date
                labelColumn for that): provide "labelColumn" (row/event name),
                "startColumn" and "endColumn" (date/timestamp columns).
                Optional "barLabelColumn", "tooltipColumn".

                Optional for any chart type: "title"?, "options"? (stacked,
                indexAxis, sortBy, sortDirection, showLegend, sliceLabel, ...).
                For type="kpi" also provide: "label", "valueColumn",
                "aggregation"?, "prefix"?, "suffix"?.

        When the user asks to CHANGE a chart you just rendered ("make it
        stacked", "use a line chart", "break it down by region"), call this tool
        again with the adjusted widget. The earlier chart is frozen — never
        describe it as if it had the new shape.

        Returns:
            JSON {"success": true, "chart_ref": "<id>", "title": ...,
            "chart_type": ...} on success, plus "series_count" (int) and
            "stacked" (bool) for type="chart". The chart renders from server-side state — do not describe
            the data values yourself, they are not visible to you. Do check
            series_count: 1 means the chart has a single series, so it is NOT
            broken down by anything and NOT visually stacked, whatever the
            options say.
            JSON {"success": false, "message": "..."} on failure — fall back
            to a normal text answer.
        """
        if not isinstance(widget, dict) or not widget.get("type"):
            return json.dumps({"success": False, "message": "widget must be a dict with a 'type' key"})

        connection_id = widget.get("connectionId")
        if not connection_id or not context.can_access_connection(connection_id):
            return json.dumps({"success": False, "message": "connectionId missing or not accessible"})

        from backend.agents.dashboard_agent.widget_specs.widgets import build_widgets
        from backend.agents.dashboard_tools import _execute_widget_sql, _verify_widgets

        hydrated = build_widgets([widget])
        if not hydrated or "widget" not in hydrated[0]:
            return json.dumps({"success": False, "message": f"unsupported widget type: {widget.get('type')}"})

        # Same pre-execution gate create_dashboard runs (unaggregated category
        # charts, unbounded scatter/bubble, dataSource shape). Without it a SQL
        # shape rejected for a dashboard still executes through chat. The
        # dashboard-level rules inside are no-ops for a single widget.
        violations = _verify_widgets(hydrated, None)
        if violations:
            return json.dumps({
                "success": False,
                "violations": violations,
                "message": "Validation failed — see violations. Fix the widget and call generate_chat_chart again.",
            })

        # Deep-copy before mutation — _execute_widget_sql merges query rows
        # into widget.config in-place; the original `widget` arg is still held
        # in the agent's message history (same rationale as create_dashboard).
        w = copy.deepcopy(hydrated[0])
        error = await _execute_widget_sql(
            w, db_session_factory, user_id=context.user_id, allow_row_sampling=False,
        )
        if error:
            return json.dumps({"success": False, "message": error})

        chart_ref = str(uuid.uuid4())
        store_query_result(chart_ref, context.user_id, {"widget": w, "connection_id": connection_id}, ttl=3600)

        wconf = w.get("widget", {}).get("config", {})
        widget_type = w.get("widget", {}).get("type")
        result = {
            "success": True,
            "chart_ref": chart_ref,
            "title": wconf.get("title") or wconf.get("label"),
            "chart_type": widget_type,
        }
        if widget_type == "chart":
            # A count and a flag, never values — enough for the reply to state what
            # the chart actually shows (a one-series "stacked by category" claim is
            # the failure this exists to stop) without putting row data in front of
            # the LLM. Only charts have series; a kpi would always report 0.
            datasets = ((wconf.get("data") or {}).get("datasets")) or []
            result["series_count"] = len(datasets)
            result["stacked"] = (wconf.get("options") or {}).get("stacked") in (
                True, "standard", "percentage",
            )
        return json.dumps(result)

    @tool
    def select_dashboard_widget(dashboard_id: int, question: str) -> str:
        """
        Pick the single existing widget on an @mentioned dashboard that best
        matches the user's question, and render it inline in this chat reply
        (live — real dashboard widget, refresh works). Use this instead of
        generate_chat_chart whenever the question refers to an @mentioned
        dashboard — it avoids building a duplicate chart.

        Args:
            dashboard_id: id of the @mentioned dashboard.
            question: the user's question, used to match against widget titles.

        Returns:
            JSON {"success": true, "dashboard_id": ..., "widget_id": ..., "title": ...}
            or {"success": false, "message": "..."} if the dashboard has no
            chartable widgets, no widget matches the question, or it isn't
            accessible. On failure fall back to generate_chat_chart (or a plain
            text answer) — never guess a widget.
        """
        from backend.api.dashboards import _dashboard_visible_to
        from backend.models.dashboard import Dashboard
        from backend.models.user import User

        db = db_session_factory()
        try:
            # Same read scope as GET /dashboards/{id} — the mention picker is fed
            # by that endpoint, so an org-readable dashboard the user can mention
            # must also be selectable here.
            user = db.query(User).filter(User.id == context.user_id).first()
            query = db.query(Dashboard).filter(Dashboard.id == dashboard_id)
            dashboard = (
                _dashboard_visible_to(query, user, db).first() if user is not None
                else query.filter(Dashboard.user_id == context.user_id).first()
            )
            if not dashboard:
                return json.dumps({"success": False, "message": "dashboard not found or not accessible"})

            candidates = [
                w for w in (dashboard.widgets or [])
                if w.get("widget", {}).get("type") in ("chart", "kpi", "table", "pivot_table")
            ]
            if not candidates:
                return json.dumps({"success": False, "message": "dashboard has no chartable widgets"})

            best = _best_title_match(candidates, question)
            if best is None:
                return json.dumps({
                    "success": False,
                    "message": "no widget on this dashboard matches the question",
                })
            wconf = best.get("widget", {}).get("config", {})
            return json.dumps({
                "success": True,
                "dashboard_id": dashboard_id,
                "widget_id": best.get("id"),
                "title": wconf.get("title") or wconf.get("label"),
            })
        finally:
            db.close()

    return [generate_chat_chart, select_dashboard_widget]


def _best_title_match(widgets: list[dict], question: str) -> Optional[dict]:
    """Pick the widget whose title/label shares the most word tokens with `question`.

    Returns None when nothing overlaps. Falling back to widgets[0] instead would
    make the answer depend on dashboard layout order and hand the user a valid-
    looking chart of the wrong metric — a no-match the caller can recover from is
    strictly better.
    """
    q_tokens = {t for t in _tokenize(question) if len(t) > 2}
    best, best_score = None, 0
    for w in widgets:
        wconf = w.get("widget", {}).get("config", {})
        title = wconf.get("title") or wconf.get("label") or ""
        score = len(q_tokens & _tokenize(title))
        if score > best_score:
            best, best_score = w, score
    return best


def _tokenize(text: str) -> set:
    return set("".join(c.lower() if c.isalnum() else " " for c in text).split())


def resolve_chart_specs_from_tool_results(
    tool_results: list[tuple[str, Any]], user_id: str,
) -> Optional[list[dict]]:
    """Turn this turn's chat-chart tool call(s) into a ChartRef list for the message.

    tool_results: [(tool_name, parsed_output), ...] in call order, covering
    ALL tools called this turn (not just chart tools — irrelevant ones are
    skipped). Uses the LAST successful chart-tool call. For generate_chat_chart,
    resolves the opaque chart_ref to the full widget via query_result_store —
    the widget's row data never appeared in `tool_results` (the tool's own
    return value is already lean).
    """
    for tool_name, output in reversed(tool_results):
        if tool_name not in _CHART_TOOL_NAMES:
            continue
        data = output
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(data, dict) or not data.get("success"):
            continue

        if tool_name == "generate_chat_chart":
            chart_ref = data.get("chart_ref")
            if not chart_ref:
                continue
            stored = get_query_result(chart_ref, user_id)
            if not stored:
                logger.warning("generate_chat_chart: chart_ref %s expired before persist", chart_ref)
                continue
            return [{
                "kind": "adhoc",
                "widget": stored["widget"],
                "connection_id": stored["connection_id"],
            }]

        dashboard_id, widget_id = data.get("dashboard_id"), data.get("widget_id")
        if not dashboard_id or not widget_id:
            continue
        return [{
            "kind": "dashboard_widget",
            "dashboard_id": dashboard_id,
            "widget_id": widget_id,
        }]

    return None
