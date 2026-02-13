from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.data_agent.prompts import DATA_AGENT_SYSTEM_PROMPT
from backend.agents.context import AgentContext
from backend.llm.factory import get_provider
from backend.config import settings
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


async def invoke_data_agent(
    question: str,
    context: AgentContext
) -> Dict[str, Any]:
    """
    Invoke stateless Data Agent for SQL query generation and execution.

    Args:
        question: User's data question
        context: AgentContext with user_id and available_connections

    Returns:
        Dict with success, message, sql_queries, results
    """
    # Build tools with captured context
    tools = build_data_agent_tools(context)

    # Get LLM provider
    provider = get_provider(settings.default_llm_provider)

    # Create stateless ReAct agent (no checkpointer - single turn)
    agent = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=DATA_AGENT_SYSTEM_PROMPT
    )

    try:
        # Invoke agent (single turn, no thread persistence)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=question)]}
        )

        # Extract SQL queries and results from messages
        messages = result.get("messages", [])
        sql_queries = []
        query_results = []

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.get("name") == "execute_query":
                        sql_queries.append(tool_call.get("args", {}).get("sql"))

            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    content_dict = json.loads(msg.content)
                    if "columns" in content_dict and "rows" in content_dict:
                        query_results.append(content_dict)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Get final answer
        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Query completed successfully",
            "sql_queries": sql_queries,
            "results": query_results
        }

    except Exception as e:
        logger.error(f"Data agent failed: {str(e)}")
        return {
            "success": False,
            "message": f"Data agent failed: {str(e)}",
            "sql_queries": [],
            "results": []
        }
