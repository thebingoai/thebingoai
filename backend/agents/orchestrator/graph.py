from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from backend.agents.orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from backend.agents.data_agent import invoke_data_agent
from backend.agents.rag_agent import invoke_rag_agent
from backend.agents.skills import get_skill_registry
from backend.agents.context import AgentContext
from backend.llm.factory import get_provider
from backend.config import settings
from typing import Dict, Any
import json
import logging
import time

logger = logging.getLogger(__name__)


def build_orchestrator_tools(context: AgentContext):
    """
    Build orchestrator tools with sub-agents as tools.

    Each sub-agent is wrapped as a tool that the orchestrator can invoke.
    Context is captured via closure for thread-safety.
    """

    @tool
    async def data_agent(question: str) -> str:
        """
        Query databases using SQL. Use for data analysis questions.

        Args:
            question: Natural language question about data

        Returns:
            JSON string with SQL queries and results
        """
        result = await invoke_data_agent(question, context)
        return json.dumps(result)

    @tool
    async def rag_agent(question: str, namespace: str = "default") -> str:
        """
        Search uploaded documents. Use for questions about documentation.

        Args:
            question: Question about documents
            namespace: Vector namespace (default: "default")

        Returns:
            JSON string with answer and source context
        """
        result = await invoke_rag_agent(question, context, namespace)
        return json.dumps(result)

    @tool
    async def recall_memory(query: str) -> str:
        """
        Recall past conversation context (Phase 06 - currently stub).

        Args:
            query: What to recall from memory

        Returns:
            JSON string with recalled context
        """
        result = {
            "success": False,
            "message": "Memory system not yet implemented (Phase 06)",
            "past_results": None
        }
        return json.dumps(result)

    # Get skills from registry
    skill_tools = get_skill_registry().to_tools()

    # Combine sub-agent tools + skill tools
    return [data_agent, rag_agent, recall_memory] + skill_tools


async def run_orchestrator(
    user_question: str,
    context: AgentContext,
    history: list = None
) -> Dict[str, Any]:
    """
    Run orchestrator agent (non-streaming).

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id

    Returns:
        Dict with success, message, metadata
    """
    # Build tools with captured context
    tools = build_orchestrator_tools(context)

    # Get LLM provider
    provider = get_provider(settings.default_llm_provider)

    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=ORCHESTRATOR_SYSTEM_PROMPT
    )

    try:
        # Build messages list from history + current message
        messages = []
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=user_question))

        result = await orchestrator.ainvoke({"messages": messages})

        # Extract final answer
        messages = result.get("messages", [])

        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Query completed successfully",
            "thread_id": context.thread_id
        }

    except Exception as e:
        logger.error(f"Orchestrator failed: {str(e)}")
        return {
            "success": False,
            "message": f"Orchestrator failed: {str(e)}",
            "thread_id": context.thread_id
        }


async def stream_orchestrator(
    user_question: str,
    context: AgentContext,
    history: list = None
):
    """
    Stream orchestrator responses using SSE event format.

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id

    Yields:
        SSE events: {"type": "status|token|done|error", "content": ...}
    """
    try:
        # Status update
        yield {"type": "status", "content": "Starting orchestrator..."}

        # Build tools with captured context
        tools = build_orchestrator_tools(context)

        # Get LLM provider
        provider = get_provider(settings.default_llm_provider)

        orchestrator = create_react_agent(
            model=provider.get_langchain_llm(),
            tools=tools,
            prompt=ORCHESTRATOR_SYSTEM_PROMPT
        )

        # Build messages list from history + current message
        messages = []
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=user_question))

        # Collect steps for persistence after streaming
        collected_steps = []
        step_number = 0

        # Track tool start times for duration computation
        step_start_times: Dict[str, float] = {}

        # Buffer tokens to avoid yielding intermediate reasoning text.
        # The ReAct loop makes multiple LLM calls: first to reason/plan (then calls a tool),
        # then to synthesize the final answer. By buffering and clearing on tool_start,
        # only the final answer tokens (after all tools complete) are flushed to the client.
        token_buffer = []

        # Track the run_id of the active LLM stream to prevent duplicate tokens.
        # LangGraph v2 astream_events propagates events at multiple hierarchy levels,
        # meaning a single token can produce multiple on_chat_model_stream events with
        # different run_ids. We lock to the first run_id seen and discard others.
        active_stream_run_id = None

        # Stream events from orchestrator
        async for event in orchestrator.astream_events(
            {"messages": messages},
            version="v2"
        ):
            kind = event.get("event")

            # Tool invocations — include args from event data
            if kind == "on_tool_start":
                # Discard buffered reasoning tokens from the planning LLM call
                token_buffer.clear()
                active_stream_run_id = None
                tool_name = event.get("name")
                tool_input = event.get("data", {}).get("input", {})
                step_start_times[tool_name] = time.time()
                step_number += 1
                step = {
                    "agent_type": "orchestrator",
                    "step_type": "tool_call",
                    "tool_name": tool_name,
                    "content": {"tool": tool_name, "args": tool_input},
                    "step_number": step_number
                }
                collected_steps.append(step)
                yield {
                    "type": "tool_call",
                    "content": {"tool": tool_name, "status": "started", "args": tool_input}
                }

            # Tool results — include parsed result data
            elif kind == "on_tool_end":
                # Discard any buffered tokens from nested LLM calls (e.g. data agent's
                # internal synthesis) so only the orchestrator's final answer remains.
                token_buffer.clear()
                active_stream_run_id = None
                tool_name = event.get("name")
                tool_output = event.get("data", {}).get("output", None)

                # Compute duration from tracked start time
                start_time = step_start_times.pop(tool_name, None)
                duration_ms = int((time.time() - start_time) * 1000) if start_time is not None else None

                # LangGraph v2 may return a ToolMessage object instead of a raw string
                if hasattr(tool_output, "content"):
                    tool_output = tool_output.content

                # Parse JSON string output from sub-agents
                parsed_output = None
                if isinstance(tool_output, str):
                    try:
                        parsed_output = json.loads(tool_output)
                    except (json.JSONDecodeError, TypeError):
                        parsed_output = tool_output
                elif tool_output is not None:
                    # Fallback: convert non-serializable types to string
                    try:
                        json.dumps(tool_output)  # test serializability
                        parsed_output = tool_output
                    except (TypeError, ValueError):
                        parsed_output = str(tool_output)
                else:
                    parsed_output = None

                step_number += 1
                step = {
                    "agent_type": "orchestrator",
                    "step_type": "tool_result",
                    "tool_name": tool_name,
                    "content": {"tool": tool_name, "result": parsed_output},
                    "step_number": step_number,
                    "duration_ms": duration_ms
                }
                collected_steps.append(step)
                yield {
                    "type": "tool_result",
                    "content": {"tool": tool_name, "status": "completed", "result": parsed_output, "duration_ms": duration_ms}
                }

            # LLM streaming tokens — buffer instead of yielding immediately.
            # Tokens before a tool_start are intermediate reasoning; token_buffer is
            # cleared on tool_start so only the final synthesis tokens remain.
            # run_id deduplication prevents the same token being buffered twice when
            # LangGraph propagates the event at multiple hierarchy levels.
            elif kind == "on_chat_model_stream":
                run_id = event.get("run_id")
                if active_stream_run_id is None:
                    active_stream_run_id = run_id
                if run_id != active_stream_run_id:
                    continue
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        token_buffer.append(content)

        # Flush the final answer tokens (only the last LLM synthesis call survives)
        for token in token_buffer:
            yield {"type": "token", "content": token}

        # Done event — include collected steps for chat.py to persist
        yield {
            "type": "done",
            "content": "Orchestrator completed",
            "thread_id": context.thread_id,
            "steps": collected_steps
        }

    except Exception as e:
        logger.error(f"Orchestrator streaming failed: {str(e)}")
        yield {
            "type": "error",
            "content": f"Orchestrator failed: {str(e)}"
        }
