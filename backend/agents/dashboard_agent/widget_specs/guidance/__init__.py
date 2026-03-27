"""Guidance constants registry for widget specs."""

from backend.agents.dashboard_agent.widget_specs.guidance.kpi import KPI_GUIDANCE
from backend.agents.dashboard_agent.widget_specs.guidance.chart import CHART_GUIDANCE
from backend.agents.dashboard_agent.widget_specs.guidance.table import TABLE_GUIDANCE
from backend.agents.dashboard_agent.widget_specs.guidance.filter import FILTER_GUIDANCE
from backend.agents.dashboard_agent.widget_specs.guidance.text import TEXT_GUIDANCE

GUIDANCE = {
    "kpi": KPI_GUIDANCE,
    "chart": CHART_GUIDANCE,
    "table": TABLE_GUIDANCE,
    "filter": FILTER_GUIDANCE,
    "text": TEXT_GUIDANCE,
}
