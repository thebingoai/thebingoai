from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QueryState(TypedDict):
    """
    Shared state for all agents (Data Agent, Orchestrator).

    LangGraph's create_react_agent manages message history automatically.
    """
    messages: Annotated[List[BaseMessage], add_messages]
