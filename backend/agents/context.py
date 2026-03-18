from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentContext:
    """
    Thread-safe agent context passed via closures.

    Replaces global variables for multi-user, multi-thread safety.
    Each agent invocation gets its own context instance.
    """
    user_id: str
    available_connections: List[int]
    thread_id: Optional[str] = None

    # Phase 4: team + policy awareness
    team_id: Optional[str] = None
    allowed_tool_keys: List[str] = field(default_factory=list)

    # Agent mesh: session identity
    session_id: Optional[str] = None

    def can_access_connection(self, connection_id: int) -> bool:
        """Check if user can access a connection."""
        return connection_id in self.available_connections

    def can_use_tool(self, tool_key: str) -> bool:
        """Check if the current team policy allows this tool_key."""
        # If no policy has been loaded yet, allow everything (backward compat)
        if not self.allowed_tool_keys:
            return True
        return tool_key in self.allowed_tool_keys
