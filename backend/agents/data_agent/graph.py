from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, ToolMessage
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.data_agent.prompts import DATA_AGENT_SYSTEM_PROMPT, build_data_agent_prompt
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
    Invoke Data Agent for SQL query generation and execution.

    When agent_mesh_enabled=True and context has a session_id, uses AgentRuntime
    for session-based execution with persistent schema knowledge across messages.

    Args:
        question: User's data question
        context: AgentContext with user_id and available_connections

    Returns:
        Dict with success, message, sql_queries, results, steps
    """
    # Build tools with captured context
    tools = build_data_agent_tools(context)

    # Use AgentRuntime when mesh is enabled for session persistence
    if settings.agent_mesh_enabled and context.session_id:
        from backend.agents.runtime import AgentRuntime
        from backend.services.agent_registry import AgentRegistry
        from backend.services.agent_message_bus import AgentMessageBus
        from backend.database.session import SessionLocal

        registry = AgentRegistry()
        db = SessionLocal()
        message_bus = AgentMessageBus(db_session=db, redis_client=registry.redis)

        runtime = AgentRuntime(
            session_id=context.session_id,
            agent_type="data_agent",
            user_id=context.user_id,
            context=context,
            registry=registry,
            message_bus=message_bus,
        )

        prompt = build_data_agent_prompt(context.available_connections)
        result = await runtime.execute(question, tools, prompt)

        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "sql_queries": [],
            "results": [],
            "steps": [],
        }

    # Get LLM provider
    provider = get_provider(settings.default_llm_provider)

    # Create stateless ReAct agent (no checkpointer - single turn)
    agent = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=build_data_agent_prompt(context.available_connections)
    )

    try:
        # Invoke agent (single turn, no thread persistence)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=question)]},
        )

        # Extract SQL queries, results, and all intermediate steps from messages
        messages = result.get("messages", [])
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

        # Get final answer (last AI message without tool calls)
        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Query completed successfully",
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
