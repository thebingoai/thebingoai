"""
AgentRuntime — wraps agent execution with session identity and communication tools.

Each agent instance is bound to a session_id and user_id. The runtime:
1. Registers/resumes the session via AgentRegistry
2. Drains the inbox (processes pending inter-agent messages)
3. Injects communication tools alongside agent-specific tools
4. Creates and invokes a ReAct agent
5. Persists results and updates session status
"""

import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage

from backend.agents.context import AgentContext
from backend.config import settings
from backend.services.agent_registry import AgentRegistry
from backend.services.agent_message_bus import AgentMessageBus

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Manages an agent's session lifecycle, inbox, and communication tools."""

    def __init__(
        self,
        session_id: str,
        agent_type: str,
        user_id: str,
        context: AgentContext,
        registry: AgentRegistry,
        message_bus: AgentMessageBus,
    ):
        self.session_id = session_id
        self.agent_type = agent_type
        self.user_id = user_id
        self.context = context
        self.registry = registry
        self.message_bus = message_bus

    async def execute(
        self,
        message: str,
        tools: list,
        system_prompt: str,
        history: Optional[list] = None,
    ) -> dict:
        """
        Execute an agent turn with session management.

        Args:
            message: The input message/request
            tools: Agent-specific LangChain tools
            system_prompt: System prompt for the agent
            history: Optional prior message history

        Returns:
            Dict with success, message, session_id
        """
        from langgraph.prebuilt import create_react_agent
        from backend.llm.factory import get_provider

        # 1. Register/resume session
        self.registry.register_session(
            user_id=self.user_id,
            session_id=self.session_id,
            agent_type=self.agent_type,
        )

        # 2. Drain inbox — process pending messages from other agents
        pending = self.message_bus.drain_inbox(self.user_id, self.session_id)
        inbox_context = ""
        if pending:
            inbox_lines = []
            for msg in pending:
                from_id = msg.get("from_session_id", "unknown")
                content = msg.get("content", {})
                text = content.get("text", json.dumps(content))
                inbox_lines.append(f"[From {from_id}]: {text}")
            inbox_context = (
                "\n\n--- Pending messages from other agents ---\n"
                + "\n".join(inbox_lines)
                + "\n--- End pending messages ---\n"
            )

        # 3. Inject communication tools
        comm_tools = self.build_communication_tools()
        all_tools = tools + comm_tools

        # 4. Build and invoke agent
        provider = get_provider(settings.default_llm_provider)

        agent = create_react_agent(
            model=provider.get_langchain_llm(),
            tools=all_tools,
            prompt=system_prompt,
        )

        messages = []
        if history:
            for msg in history:
                if isinstance(msg, dict):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    else:
                        messages.append(AIMessage(content=content))
                else:
                    messages.append(msg)

        full_message = inbox_context + message if inbox_context else message
        messages.append(HumanMessage(content=full_message))

        try:
            result = await agent.ainvoke({"messages": messages})

            # Extract final answer
            result_messages = result.get("messages", [])
            final_answer = None
            for msg in reversed(result_messages):
                if hasattr(msg, "type") and msg.type == "ai" and not getattr(msg, "tool_calls", None):
                    final_answer = msg.content
                    break

            # 5. Update session status
            self.registry.heartbeat(self.session_id)

            return {
                "success": True,
                "message": final_answer or "Completed",
                "session_id": self.session_id,
            }

        except Exception as e:
            logger.error(
                "AgentRuntime execution failed (session=%s, type=%s): %s",
                self.session_id, self.agent_type, e,
            )
            self.registry.update_status(self.session_id, "idle")
            return {
                "success": False,
                "message": f"Agent execution failed: {e}",
                "session_id": self.session_id,
            }

    def build_communication_tools(self) -> list:
        """
        Build LangChain tools for inter-agent communication.

        All tools are scoped to self.user_id — agent can only see/message
        agents belonging to the same user.
        """
        from backend.agents.communication_tools import build_communication_tools

        return build_communication_tools(
            user_id=self.user_id,
            session_id=self.session_id,
            message_bus=self.message_bus,
            registry=self.registry,
        )
