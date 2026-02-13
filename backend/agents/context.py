from dataclasses import dataclass
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

    def can_access_connection(self, connection_id: int) -> bool:
        """Check if user can access a connection."""
        return connection_id in self.available_connections
