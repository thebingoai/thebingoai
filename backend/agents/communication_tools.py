"""
Inter-agent communication tools (user-scoped).

These LangChain tools are injected into agents by AgentRuntime, enabling
peer-to-peer discovery and messaging within the same user's agent mesh.
"""

import json
import logging
from typing import Optional

from langchain_core.tools import tool

from backend.services.agent_registry import AgentRegistry
from backend.services.agent_message_bus import AgentMessageBus

logger = logging.getLogger(__name__)


def build_communication_tools(
    user_id: str,
    session_id: str,
    message_bus: AgentMessageBus,
    registry: AgentRegistry,
) -> list:
    """
    Build a list of LangChain tools for inter-agent communication.

    All tools are scoped to the given user_id. An agent can only
    discover and message other agents belonging to the same user.

    Args:
        user_id: The owning user's ID
        session_id: This agent's session ID
        message_bus: AgentMessageBus instance
        registry: AgentRegistry instance

    Returns:
        List of LangChain tools [sessions_list, sessions_send, sessions_history, sessions_broadcast]
    """

    @tool
    def sessions_list(filter_type: str = "") -> str:
        """
        List active agent sessions belonging to this user.

        Args:
            filter_type: Optional agent type filter (e.g. "data_agent", "dashboard_agent").
                        Empty string means all types.

        Returns:
            JSON array of active sessions with id, agent_type, status, capabilities
        """
        from backend.services.agent_discovery import AgentDiscovery

        discovery = AgentDiscovery(redis_client=registry.redis)
        ft = filter_type if filter_type else None
        sessions = discovery.list_sessions(user_id, filter_type=ft)
        return json.dumps([
            {
                "session_id": s.get("session_id"),
                "agent_type": s.get("agent_type"),
                "status": s.get("status"),
                "capabilities": s.get("capabilities", {}),
            }
            for s in sessions
        ])

    @tool
    def sessions_send(
        to_session_id: str,
        message: str,
        wait_for_response: bool = True,
    ) -> str:
        """
        Send a message to another agent session owned by this user.

        Use this to delegate work to specialist agents (e.g. ask the data_agent
        to list tables or run a SQL query).

        Args:
            to_session_id: Target agent's session ID (from sessions_list)
            message: The message/request to send
            wait_for_response: If True, blocks up to 60s for a response.
                             If False, sends fire-and-forget.

        Returns:
            JSON with the response content (if wait_for_response=True),
            or confirmation of send (if False)
        """
        content = {"text": message}

        if wait_for_response:
            response = message_bus.send_and_wait(
                user_id=user_id,
                from_session_id=session_id,
                to_session_id=to_session_id,
                content=content,
                timeout=60,
            )
            if response is None:
                return json.dumps({
                    "success": False,
                    "message": "Timeout waiting for agent response (60s)",
                })
            return json.dumps({"success": True, "response": response})
        else:
            msg_id = message_bus.send(
                user_id=user_id,
                from_session_id=session_id,
                to_session_id=to_session_id,
                content=content,
                message_type="notification",
            )
            return json.dumps({
                "success": True,
                "message_id": msg_id,
                "message": "Sent successfully",
            })

    @tool
    def sessions_history(session_id_filter: str = "", limit: int = 20) -> str:
        """
        Get message history for a session.

        Args:
            session_id_filter: Session ID to get history for. Empty = this session.
            limit: Max messages to return (default 20)

        Returns:
            JSON array of messages with from/to, type, content, timestamp
        """
        target_session = session_id_filter if session_id_filter else session_id
        history = message_bus.get_history(
            user_id=user_id,
            session_id=target_session,
            limit=limit,
        )
        return json.dumps(history)

    @tool
    def sessions_broadcast(message: str, filter_type: str = "") -> str:
        """
        Broadcast a message to all of this user's active agents (except self).

        Args:
            message: The message to broadcast
            filter_type: Optional agent type filter. Empty = all agents.

        Returns:
            JSON with count of messages sent
        """
        content = {"text": message}
        ft = filter_type if filter_type else None
        msg_ids = message_bus.broadcast(
            user_id=user_id,
            from_session_id=session_id,
            content=content,
            filter_type=ft,
        )
        return json.dumps({
            "success": True,
            "messages_sent": len(msg_ids),
        })

    return [sessions_list, sessions_send, sessions_history, sessions_broadcast]
