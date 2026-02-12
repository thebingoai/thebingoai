from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from backend.database.base import Base
from datetime import datetime
import enum


class StepType(str, enum.Enum):
    """Type of agent step."""
    REASONING = "reasoning"        # LLM deciding what to do
    TOOL_CALL = "tool_call"        # Tool invocation (action)
    TOOL_RESULT = "tool_result"    # Tool response (result)
    FINAL_ANSWER = "final_answer"  # Final synthesized answer


class AgentType(str, enum.Enum):
    """Which agent produced the step."""
    ORCHESTRATOR = "orchestrator"
    DATA_AGENT = "data_agent"
    RAG_AGENT = "rag_agent"
    SKILL = "skill"


class AgentStep(Base):
    """
    Individual step in agent execution.

    Captures the full reasoning chain:
    - What the LLM thought (reasoning)
    - What tool it called (tool_call)
    - What result it got (tool_result)
    - Final answer (final_answer)

    Frontend can display this as a collapsible "thinking chain".
    """
    __tablename__ = "agent_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    step_number = Column(Integer, nullable=False)       # Order within the message
    agent_type = Column(Enum(AgentType), nullable=False) # Which agent produced this step
    step_type = Column(Enum(StepType), nullable=False)   # reasoning/tool_call/tool_result/final
    tool_name = Column(String, nullable=True)            # e.g. "data_agent", "execute_query", "enrich_with_history"
    content = Column(JSON, nullable=False)               # Flexible: reasoning text, tool args, results
    duration_ms = Column(Integer, nullable=True)         # How long this step took
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("Message", back_populates="agent_steps")


# Example content JSON by step_type:
#
# REASONING:
# {
#     "text": "User is asking about data. I should call data_agent.",
#     "decision": "route_to_data_agent"
# }
#
# TOOL_CALL:
# {
#     "tool": "data_agent",
#     "args": {"question": "How many users we have?"}
# }
#
# TOOL_RESULT:
# {
#     "tool": "data_agent",
#     "success": true,
#     "result": {"message": "142 users", "sql_queries": [...], "results": [...]}
# }
#
# FINAL_ANSWER:
# {
#     "text": "We have 142 users. Compared to 2 weeks ago (120 users), that's an 18% increase."
# }
