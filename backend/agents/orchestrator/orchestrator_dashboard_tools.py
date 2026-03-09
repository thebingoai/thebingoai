from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.agents.dashboard_agent import invoke_dashboard_agent
from typing import List, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)


def build_dashboard_tools(context: AgentContext, db_session_factory: Optional[Callable] = None) -> List:
    """Return [create_dashboard] tool when db_session_factory is available."""
    if db_session_factory is None:
        return []

    @tool
    async def create_dashboard(request: str) -> str:
        """
        Create a persistent, fully-featured dashboard from a natural language request.

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

        Use this tool whenever the user asks to create, build, or make a dashboard — even if
        they have not specified exact metrics, charts, or data sources. The sub-agent will
        autonomously determine what data is available and what visualisations are appropriate.
        There is no need to ask the user for detailed requirements upfront.

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
        result = await invoke_dashboard_agent(request, context, db_session_factory)
        return json.dumps(result)

    return [create_dashboard]
