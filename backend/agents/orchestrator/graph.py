from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from backend.agents.orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT, build_orchestrator_prompt
from backend.agents.data_agent import invoke_data_agent
from backend.agents.rag_agent import invoke_rag_agent
from backend.agents.skills import get_skill_registry
from backend.agents.context import AgentContext
from backend.agents.tool_registry import build_tools_for_keys
from backend.llm.factory import get_provider
from backend.config import settings
from typing import Dict, Any, List, Optional, TYPE_CHECKING
import json
import logging
import time

if TYPE_CHECKING:
    from backend.models.custom_agent import CustomAgent

logger = logging.getLogger(__name__)


def build_orchestrator_tools(context: AgentContext, custom_agents: Optional[List["CustomAgent"]] = None):
    """
    Build orchestrator tools.

    When custom_agents is provided (Phase 4), each custom agent is wrapped as a
    single tool for the orchestrator to invoke. Runtime enforcement filters out
    tools and connections that are no longer in the team's policy.

    When custom_agents is None or empty, falls back to the legacy static tools
    (data_agent, rag_agent, recall_memory + skills) for backward compatibility.
    """
    if custom_agents:
        return _build_dynamic_tools(context, custom_agents)
    return _build_legacy_tools(context)


def _build_legacy_tools(context: AgentContext):
    """Legacy static tools used when no custom agents are configured."""

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


def _build_dynamic_tools(context: AgentContext, custom_agents: List["CustomAgent"]) -> List:
    """
    Build one tool per custom agent definition.

    Each custom agent is wrapped as a single callable tool. At build time the
    effective tool set is computed by intersecting the agent's stored tool_keys
    with the team's current allowed_tool_keys (runtime enforcement).
    """
    provider = get_provider(settings.default_llm_provider)
    tools = []

    for agent_def in custom_agents:
        # Runtime enforcement: intersect stored keys with current team policy
        effective_tool_keys = [
            k for k in (agent_def.tool_keys or [])
            if context.can_use_tool(k)
        ]
        effective_connection_ids = [
            c for c in (agent_def.connection_ids or [])
            if context.can_access_connection(c)
        ]

        # Scoped context for this sub-agent
        agent_context = AgentContext(
            user_id=context.user_id,
            available_connections=effective_connection_ids,
            thread_id=context.thread_id,
            team_id=context.team_id,
            allowed_tool_keys=effective_tool_keys,
        )

        # Build the concrete LangChain tools for this agent
        agent_tools = build_tools_for_keys(effective_tool_keys, agent_context)

        agent_name = agent_def.name
        agent_description = agent_def.description or f"Custom agent: {agent_name}"
        agent_system_prompt = agent_def.system_prompt

        @tool(name=agent_name, description=agent_description)
        async def invoke_custom_agent(
            question: str,
            _system_prompt: str = agent_system_prompt,
            _tools: list = agent_tools,
            _ctx: AgentContext = agent_context,
        ) -> str:
            """Invoke a custom sub-agent with its configured tools."""
            sub_agent = create_react_agent(
                model=provider.get_langchain_llm(),
                tools=_tools,
                prompt=_system_prompt,
            )
            try:
                result = await sub_agent.ainvoke({"messages": [HumanMessage(content=question)]})
                messages = result.get("messages", [])
                final_answer = None
                for msg in reversed(messages):
                    if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                        final_answer = msg.content
                        break
                return json.dumps({"success": True, "message": final_answer or "Completed"})
            except Exception as exc:
                logger.error(f"Custom agent '{agent_name}' failed: {exc}")
                return json.dumps({"success": False, "message": str(exc)})

        tools.append(invoke_custom_agent)

    return tools


async def run_orchestrator(
    user_question: str,
    context: AgentContext,
    history: list = None,
    custom_agents: Optional[List["CustomAgent"]] = None,
) -> Dict[str, Any]:
    """
    Run orchestrator agent (non-streaming).

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id
        custom_agents: Optional list of active CustomAgent records for this user

    Returns:
        Dict with success, message, metadata
    """
    tools = build_orchestrator_tools(context, custom_agents)
    prompt = build_orchestrator_prompt(custom_agents) if custom_agents else ORCHESTRATOR_SYSTEM_PROMPT

    provider = get_provider(settings.default_llm_provider)

    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        prompt=prompt,
    )

    try:
        messages = []
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=user_question))

        result = await orchestrator.ainvoke({"messages": messages})

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
    history: list = None,
    custom_agents: Optional[List["CustomAgent"]] = None,
):
    """
    Stream orchestrator responses using SSE event format.

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id
        custom_agents: Optional list of active CustomAgent records for this user

    Yields:
        SSE events: {"type": "status|token|done|error", "content": ...}
    """
    try:
        yield {"type": "status", "content": "Starting orchestrator..."}

        tools = build_orchestrator_tools(context, custom_agents)
        prompt = build_orchestrator_prompt(custom_agents) if custom_agents else ORCHESTRATOR_SYSTEM_PROMPT

        provider = get_provider(settings.default_llm_provider)

        orchestrator = create_react_agent(
            model=provider.get_langchain_llm(),
            tools=tools,
            prompt=prompt,
        )

        messages = []
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=user_question))

        collected_steps = []
        step_number = 0
        step_start_times: Dict[str, float] = {}
        token_buffer = []
        active_stream_run_id = None

        async for event in orchestrator.astream_events(
            {"messages": messages},
            version="v2"
        ):
            kind = event.get("event")

            if kind == "on_tool_start":
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

            elif kind == "on_tool_end":
                token_buffer.clear()
                active_stream_run_id = None
                tool_name = event.get("name")
                tool_output = event.get("data", {}).get("output", None)

                start_time = step_start_times.pop(tool_name, None)
                duration_ms = int((time.time() - start_time) * 1000) if start_time is not None else None

                if hasattr(tool_output, "content"):
                    tool_output = tool_output.content

                parsed_output = None
                if isinstance(tool_output, str):
                    try:
                        parsed_output = json.loads(tool_output)
                    except (json.JSONDecodeError, TypeError):
                        parsed_output = tool_output
                elif tool_output is not None:
                    try:
                        json.dumps(tool_output)
                        parsed_output = tool_output
                    except (TypeError, ValueError):
                        parsed_output = str(tool_output)

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

        for token in token_buffer:
            yield {"type": "token", "content": token}

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
