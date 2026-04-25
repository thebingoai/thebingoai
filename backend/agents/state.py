from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from backend.schemas.chat import ResolvedMention


class QueryState(TypedDict, total=False):
    """
    Shared state for all agents (Data Agent, Orchestrator).

    LangGraph's create_react_agent manages message history automatically.

    Optional fields (total=False so existing flows don't have to populate them):
      mentions — @-mentions resolved client-side; orchestrator uses them as
                 scope hints when routing to sub-agents.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    mentions: List[ResolvedMention]
