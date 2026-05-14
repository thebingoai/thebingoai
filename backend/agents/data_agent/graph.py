from langchain_core.messages import ToolMessage
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.data_agent.prompts import DATA_AGENT_SYSTEM_PROMPT, build_data_agent_prompt
from backend.agents.invoke_helpers import extract_final_answer, run_inline_react, run_via_mesh_runtime
from backend.agents.loop_detector import make_loop_detector
from backend.agents.prompt_resolver import resolve_agent_prompt
from backend.agents.context import AgentContext
from backend.llm.base import BaseLLMProvider
from backend.config import settings
from typing import Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


def _resolve_data_agent_prompt(context: AgentContext, db_session_factory=None) -> str:
    """Resolve data_agent prompt from profile or fallback to legacy."""
    return resolve_agent_prompt(
        agent_type="data_agent",
        context=context,
        db_session_factory=db_session_factory,
        fallback=lambda: build_data_agent_prompt(
            context.available_connections, context.connection_metadata
        ),
        log_prefix=__name__,
    )


async def invoke_data_agent(
    question: str,
    context: AgentContext,
    llm_provider: Optional[BaseLLMProvider] = None,
) -> Dict[str, Any]:
    """
    Invoke Data Agent for SQL query generation and execution.

    When agent_mesh_enabled=True and context has a session_id, uses AgentRuntime
    for session-based execution with persistent schema knowledge across messages.

    Args:
        question: User's data question
        context: AgentContext with user_id and available_connections

    Returns:
        Dict with success, message, sql_queries, results, steps
    """
    tools = build_data_agent_tools(context)

    if settings.agent_mesh_enabled and context.session_id:
        result = await run_via_mesh_runtime(
            agent_type="data_agent",
            user_id=context.user_id,
            session_id=context.session_id,
            context=context,
            message=question,
            tools=tools,
            system_prompt=_resolve_data_agent_prompt(context),
        )
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "sql_queries": [],
            "results": [],
            "steps": [],
        }

    try:
        messages = await run_inline_react(
            tools=tools,
            system_prompt=_resolve_data_agent_prompt(context),
            message=question,
            llm_provider=llm_provider,
            pre_model_hook=make_loop_detector(max_repeats=2, max_total_calls=25),
            agent_type="data_agent",
            user_id=getattr(context, "user_id", None),
            session_id=getattr(context, "session_id", None),
        )

        sql_queries = []
        query_results = []
        steps = []

        # Index tool_call_id -> {name, args} for matching with ToolMessage results
        tool_call_index: Dict[str, Dict] = {}

        for msg in messages:
            # AI messages with tool calls — record each as a tool_call step
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = tool_call.get("name")
                    args = tool_call.get("args", {})
                    tool_call_id = tool_call.get("id", "")

                    tool_call_index[tool_call_id] = {"name": tool_name, "args": args}

                    if tool_name == "execute_query":
                        sql = args.get("sql")
                        if sql:
                            sql_queries.append(sql)

                    steps.append({
                        "agent_type": "data_agent",
                        "step_type": "tool_call",
                        "tool_name": tool_name,
                        "content": {"args": args}
                    })

            # Tool result messages — match back to the tool call
            elif isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", "")
                call_info = tool_call_index.get(tool_call_id, {})
                tool_name = call_info.get("name", "unknown")

                result_data = None
                if isinstance(msg.content, str):
                    try:
                        result_data = json.loads(msg.content)
                    except (json.JSONDecodeError, TypeError):
                        result_data = msg.content
                else:
                    result_data = msg.content

                # Collect execute_query structured results
                if tool_name == "execute_query" and isinstance(result_data, dict):
                    if "columns" in result_data and "rows" in result_data:
                        query_results.append(result_data)

                steps.append({
                    "agent_type": "data_agent",
                    "step_type": "tool_result",
                    "tool_name": tool_name,
                    "content": {"result": result_data}
                })

        return {
            "success": True,
            "message": extract_final_answer(messages) or "Query completed successfully",
            "sql_queries": sql_queries,
            "results": query_results,
            "steps": steps
        }

    except Exception as e:
        logger.error(f"Data agent failed: {str(e)}")
        return {
            "success": False,
            "message": f"Data agent failed: {str(e)}",
            "sql_queries": [],
            "results": [],
            "steps": []
        }
