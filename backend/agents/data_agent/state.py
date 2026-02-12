"""State definition for Data Agent."""

from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QueryState(TypedDict):
    """
    State for ReAct data agent.

    Note: ReAct agents work through messages and tool calls.
    LangGraph's create_react_agent handles message management via add_messages reducer.
    """

    messages: Annotated[List[BaseMessage], add_messages]
