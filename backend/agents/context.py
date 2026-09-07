from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ConnectionInfo:
    """Lightweight metadata for a database connection."""
    id: int
    name: str
    db_type: str
    database: str


@dataclass
class AgentContext:
    """
    Thread-safe agent context passed via closures.

    Replaces global variables for multi-user, multi-thread safety.
    Each agent invocation gets its own context instance.
    """
    user_id: str
    available_connections: List[int]
    connection_metadata: List[ConnectionInfo] = field(default_factory=list)
    thread_id: Optional[str] = None

    # Phase 4: team + policy awareness
    team_id: Optional[str] = None
    allowed_tool_keys: List[str] = field(default_factory=list)

    # Agent mesh: session identity
    session_id: Optional[str] = None

    # The chat turn that owns this run. Stamped on every query.result the turn
    # publishes so the browser can tell its own results from another tab's or
    # a briefing's — the side-channel is a per-user broadcast. None outside chat.
    request_id: Optional[str] = None

    # Briefing mode: set when orchestrator is running for a scheduled briefing
    briefing_id: Optional[int] = None  # set when running orchestrator for a briefing

    # Single-connection focus: set when the user explicitly scoped this turn to
    # one connection (e.g. via connection_ids from the onboarding first-question
    # flow). Renders a "Primary connection to use" hint in the orchestrator
    # system prompt so the LLM doesn't misroute to a different connection
    # (such as a seeded sample connection).
    target_connection_id: Optional[int] = None

    # Set True by create_dataset_from_upload when a fresh dataset is ingested this
    # turn. update_dashboard refuses while set: an upload+generate turn must CREATE
    # a new dashboard, never overwrite a pre-existing one the LLM happened to find.
    dataset_created_this_turn: bool = False

    def can_access_connection(self, connection_id: int) -> bool:
        """Check if user can access a connection."""
        return connection_id in self.available_connections

    def can_use_tool(self, tool_key: str) -> bool:
        """Check if the current team policy allows this tool_key."""
        # If no policy has been loaded yet, allow everything (backward compat)
        if not self.allowed_tool_keys:
            return True
        return tool_key in self.allowed_tool_keys
