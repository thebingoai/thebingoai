# Phase 04: Agent Orchestration (Orchestrator + Sub-Agents + Skills)

## Objective

Build orchestrator-based agent architecture where a main Orchestrator routes to specialized sub-agents (Data Agent, RAG Agent) and skills via tool calls. Uses closure-based context for thread-safety (no globals). Single communication channel via Nuxt frontend.

**Architecture Pattern**: Similar to OpenClaw's gateway but single-channel (Nuxt only, no multi-channel messaging).

## Prerequisites

- Phase 03: Database Connectors (schema JSON files, query execution)

## Files to Create

### Core Architecture
- `backend/agents/__init__.py` - Export agent classes and context
- `backend/agents/context.py` - AgentContext dataclass for closure-based context
- `backend/agents/state.py` - QueryState TypedDict for LangGraph

### Data Agent (Section 4A)
- `backend/agents/data_agent/tools.py` - Closure-based tools (list_tables, get_table_schema, search_tables, execute_query)
- `backend/agents/data_agent/prompts.py` - Data Agent system prompt
- `backend/agents/data_agent/__init__.py` - Export invoke_data_agent

### RAG Agent Wrapper (Section 4B)
- `backend/agents/rag_agent/__init__.py` - Wrapper around existing langgraph/runner.py

### Skills Framework (Section 4C)
- `backend/agents/skills/base.py` - BaseSkill abstract class
- `backend/agents/skills/registry.py` - SkillRegistry for dynamic skill loading
- `backend/agents/skills/summarize.py` - Example SummarizeSkill
- `backend/agents/skills/enrich_with_history.py` - EnrichWithHistorySkill (compare current data with past results)
- `backend/agents/skills/__init__.py` - Export skills framework

### Step Collection (Section 4E)
- `backend/agents/step_collector.py` - StepCollector and StepRecord for agent execution tracing

### Orchestrator (Section 4D)
- `backend/agents/orchestrator/prompts.py` - Orchestrator system prompt
- `backend/agents/orchestrator/runner.py` - Main orchestrator with sub-agents as tools
- `backend/agents/orchestrator/__init__.py` - Export run_orchestrator, stream_orchestrator

### Tests
- `backend/tests/test_data_agent_tools.py` - Unit tests for data agent tools
- `backend/tests/test_orchestrator.py` - Integration tests for orchestrator
- `backend/tests/test_skills.py` - Tests for skills framework

## Files to Modify

- None (self-contained agent module)

## Implementation Details

### 1. Agent Context (backend/agents/context.py)

Closure-based context for thread-safe operation without globals:

```python
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
```

### 2. Query State (backend/agents/state.py)

```python
from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class QueryState(TypedDict):
    """
    Shared state for all agents (Data Agent, Orchestrator).

    LangGraph's create_react_agent manages message history automatically.
    """
    messages: Annotated[List[BaseMessage], add_messages]
```

---

## Section 4A: Data Agent (Stateless ReAct Agent)

### Data Agent Tools (backend/agents/data_agent/tools.py)

**Key Pattern**: Tools created via closures with captured context (no globals):

```python
from langchain_core.tools import tool
from typing import List, Dict, Any, Callable
from backend.services.schema_discovery import load_schema_file
from backend.connectors.factory import get_connector
from backend.database.session import SessionLocal
from backend.models.database_connection import DatabaseConnection
from backend.agents.context import AgentContext
import logging

logger = logging.getLogger(__name__)


def build_data_agent_tools(context: AgentContext) -> List[Callable]:
    """
    Build data agent tools with captured context via closure.

    Each tool instance captures its own AgentContext, enabling:
    - Thread-safe operation (no shared global state)
    - Multiple concurrent agent invocations
    - Clean separation of user contexts

    Args:
        context: AgentContext with user_id and available_connections

    Returns:
        List of LangChain tool functions with context captured
    """

    @tool
    def list_tables(connection_id: int) -> List[str]:
        """
        List all tables in a database connection.

        Args:
            connection_id: Database connection ID

        Returns:
            List of table names
        """
        if not context.can_access_connection(connection_id):
            return []

        try:
            schema_json = load_schema_file(connection_id)
            return schema_json.get("table_names", [])
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return []


    @tool
    def get_table_schema(connection_id: int, table_name: str) -> Dict[str, Any]:
        """
        Get detailed schema for a specific table.

        Args:
            connection_id: Database connection ID
            table_name: Name of the table

        Returns:
            Dict with columns (name, type, nullable, primary_key, foreign_key)
            and row_count
        """
        if not context.can_access_connection(connection_id):
            return {}

        try:
            schema_json = load_schema_file(connection_id)

            # Search for table in all schemas
            for schema_name, schema_data in schema_json.get("schemas", {}).items():
                if table_name in schema_data.get("tables", {}):
                    table_data = schema_data["tables"][table_name]
                    return {
                        "table_name": table_name,
                        "schema": schema_name,
                        "columns": table_data.get("columns", []),
                        "row_count": table_data.get("row_count", 0)
                    }

            return {}
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return {}


    @tool
    def search_tables(connection_id: int, keyword: str) -> List[str]:
        """
        Search for tables/columns matching a keyword.

        Args:
            connection_id: Database connection ID
            keyword: Search keyword (case-insensitive)

        Returns:
            List of matching table names
        """
        if not context.can_access_connection(connection_id):
            return []

        try:
            schema_json = load_schema_file(connection_id)
            keyword_lower = keyword.lower()
            matches = []

            # Search table names
            for table_name in schema_json.get("table_names", []):
                if keyword_lower in table_name.lower():
                    matches.append(table_name)
                    continue

                # Search column names
                for schema_name, schema_data in schema_json.get("schemas", {}).items():
                    if table_name in schema_data.get("tables", {}):
                        table_data = schema_data["tables"][table_name]
                        for column in table_data.get("columns", []):
                            if keyword_lower in column.get("name", "").lower():
                                matches.append(table_name)
                                break

            return list(set(matches))  # Remove duplicates
        except FileNotFoundError:
            logger.warning(f"Schema file not found for connection {connection_id}")
            return []


    @tool
    def execute_query(connection_id: int, sql: str) -> Dict[str, Any]:
        """
        Execute a read-only SQL query.

        Args:
            connection_id: Database connection ID
            sql: SQL query string (SELECT only)

        Returns:
            Dict with columns, rows, row_count, execution_time_ms, or error message
        """
        if not context.can_access_connection(connection_id):
            return {"error": "Connection not authorized"}

        # Get connection details
        db = SessionLocal()
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
                DatabaseConnection.user_id == context.user_id
            ).first()

            if not connection:
                return {"error": "Connection not found"}

            # Execute query
            with get_connector(
                db_type=connection.db_type,
                host=connection.host,
                port=connection.port,
                database=connection.database,
                username=connection.username,
                password=connection.password
            ) as connector:
                result = connector.execute_query(sql)

                return {
                    "columns": result.columns,
                    "rows": [list(row) for row in result.rows],
                    "row_count": result.row_count,
                    "execution_time_ms": result.execution_time_ms
                }

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return {"error": str(e)}
        finally:
            db.close()


    # Return list of tools with captured context
    return [list_tables, get_table_schema, search_tables, execute_query]
```

### Data Agent Prompt (backend/agents/data_agent/prompts.py)

```python
DATA_AGENT_SYSTEM_PROMPT = """You are a specialized SQL query agent focused on data retrieval.

Your job is to:
1. Explore database schemas using available tools
2. Generate accurate SQL queries based on user questions
3. Execute queries and return results
4. Self-correct if queries fail

Available tools:
- list_tables(connection_id): List all tables in a connection
- get_table_schema(connection_id, table_name): Get columns and types for a table
- search_tables(connection_id, keyword): Search for tables/columns by keyword
- execute_query(connection_id, sql): Execute a SELECT query

Guidelines:
1. **Explore first**: Always use search_tables or list_tables before writing SQL
2. **Check schemas**: Use get_table_schema to understand column names and types
3. **Read-only**: Generate SELECT queries only - no INSERT/UPDATE/DELETE
4. **Self-correct**: If a query fails, analyze the error and try again
5. **Limit results**: Use LIMIT 1000 for large result sets
6. **Join properly**: Use foreign key relationships from schema when joining

When answering:
- Show which tables you explored and why you chose them
- Include the SQL queries you executed
- Present results clearly
- If a query fails, explain the error and your correction

You are stateless - focus only on the current data request."""
```

### Data Agent Invocation (backend/agents/data_agent/__init__.py)

```python
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.data_agent.prompts import DATA_AGENT_SYSTEM_PROMPT
from backend.agents.context import AgentContext
from backend.agents.state import QueryState
from backend.llm.factory import get_llm_provider
from backend.config import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def invoke_data_agent(
    question: str,
    context: AgentContext
) -> Dict[str, Any]:
    """
    Invoke stateless Data Agent for SQL query generation and execution.

    Args:
        question: User's data question
        context: AgentContext with user_id and available_connections

    Returns:
        Dict with success, message, sql_queries, results
    """
    # Build tools with captured context
    tools = build_data_agent_tools(context)

    # Get LLM provider
    provider = get_llm_provider(settings.default_llm_provider)

    # Create stateless ReAct agent (no checkpointer - single turn)
    agent = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        state_modifier=DATA_AGENT_SYSTEM_PROMPT
    )

    try:
        # Invoke agent (single turn, no thread persistence)
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=question)]}
        )

        # Extract SQL queries and results from messages
        messages = result.get("messages", [])
        sql_queries = []
        query_results = []

        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.get("name") == "execute_query":
                        sql_queries.append(tool_call.get("args", {}).get("sql"))

            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    import json
                    content_dict = json.loads(msg.content)
                    if "columns" in content_dict and "rows" in content_dict:
                        query_results.append(content_dict)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Get final answer
        final_answer = None
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai" and not hasattr(msg, "tool_calls"):
                final_answer = msg.content
                break

        return {
            "success": True,
            "message": final_answer or "Query completed successfully",
            "sql_queries": sql_queries,
            "results": query_results
        }

    except Exception as e:
        logger.error(f"Data agent failed: {str(e)}")
        return {
            "success": False,
            "message": f"Data agent failed: {str(e)}",
            "sql_queries": [],
            "results": []
        }


__all__ = ["invoke_data_agent"]
```

---

## Section 4B: RAG Agent Wrapper

### RAG Agent Wrapper (backend/agents/rag_agent/__init__.py)

Wraps existing `langgraph/runner.py` functionality:

```python
from backend.langgraph.runner import run_rag_query
from backend.agents.context import AgentContext
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def invoke_rag_agent(
    question: str,
    context: AgentContext,
    namespace: str = "default"
) -> Dict[str, Any]:
    """
    Invoke existing RAG system for document-based queries.

    Wraps backend.langgraph.runner.run_rag_query() with agent context.

    Args:
        question: User's question about documents
        context: AgentContext (thread_id used if provided)
        namespace: Vector namespace for document search

    Returns:
        Dict with success, message, context (retrieved chunks)
    """
    try:
        # Use existing RAG runner
        result = await run_rag_query(
            question=question,
            thread_id=context.thread_id or "default",
            namespace=namespace
        )

        return {
            "success": True,
            "message": result.get("answer", "No answer generated"),
            "context": result.get("context", [])
        }

    except Exception as e:
        logger.error(f"RAG agent failed: {str(e)}")
        return {
            "success": False,
            "message": f"RAG agent failed: {str(e)}",
            "context": []
        }


__all__ = ["invoke_rag_agent"]
```

---

## Section 4C: Skills Framework

### Base Skill (backend/agents/skills/base.py)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseSkill(ABC):
    """
    Abstract base class for agent skills.

    Skills are specialized tools that can be registered dynamically
    and invoked by the orchestrator when needed.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name for tool registration."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what the skill does (shown to LLM)."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute the skill with given parameters.

        Returns:
            Dict with success, message, and any additional data
        """
        pass

    def to_tool(self):
        """
        Convert skill to LangChain tool.

        Returns a tool function that wraps execute().
        """
        from langchain_core.tools import tool

        @tool(name=self.name, description=self.description)
        async def skill_tool(**kwargs) -> Dict[str, Any]:
            return await self.execute(**kwargs)

        return skill_tool
```

### Skill Registry (backend/agents/skills/registry.py)

```python
from typing import Dict, List
from backend.agents.skills.base import BaseSkill
import logging

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry for dynamically loading and managing agent skills.

    Skills can be registered at startup or runtime and converted
    to LangChain tools for orchestrator use.
    """

    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill):
        """Register a skill."""
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> BaseSkill:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        """List all registered skill names."""
        return list(self._skills.keys())

    def to_tools(self) -> List:
        """
        Convert all registered skills to LangChain tools.

        Returns:
            List of tool functions for orchestrator
        """
        return [skill.to_tool() for skill in self._skills.values()]


# Global registry instance
_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """Get global skill registry."""
    return _registry
```

### Example Skill (backend/agents/skills/summarize.py)

```python
from backend.agents.skills.base import BaseSkill
from backend.llm.factory import get_llm_provider
from backend.config import settings
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class SummarizeSkill(BaseSkill):
    """Skill for summarizing text content."""

    @property
    def name(self) -> str:
        return "summarize_text"

    @property
    def description(self) -> str:
        return "Summarize long text content into key points. Args: text (str)"

    async def execute(self, text: str) -> Dict[str, Any]:
        """
        Summarize text using LLM.

        Args:
            text: Text to summarize

        Returns:
            Dict with success, summary
        """
        try:
            provider = get_llm_provider(settings.default_llm_provider)

            prompt = f"Summarize the following text in 3-5 bullet points:\n\n{text}"

            response = await provider.chat([{"role": "user", "content": prompt}])

            return {
                "success": True,
                "summary": response
            }

        except Exception as e:
            logger.error(f"Summarize skill failed: {str(e)}")
            return {
                "success": False,
                "summary": f"Failed to summarize: {str(e)}"
            }
```

### EnrichWithHistory Skill (backend/agents/skills/enrich_with_history.py)

```python
from backend.agents.skills.base import BaseSkill
from typing import Dict, Any
import logging
import re

logger = logging.getLogger(__name__)


class EnrichWithHistorySkill(BaseSkill):
    """
    Skill for enriching current data with historical comparison.

    Call AFTER getting fresh data from data_agent to add context
    about how the data has changed over time.
    """

    @property
    def name(self) -> str:
        return "enrich_with_history"

    @property
    def description(self) -> str:
        return """Compare current data with historical results. Use AFTER data_agent returns results.
        Args: current_data (str) - the fresh data result, question (str) - the original question"""

    async def execute(self, current_data: str, question: str) -> Dict[str, Any]:
        """
        Enrich current data with historical comparison.

        Args:
            current_data: Fresh data result from data_agent
            question: The original user question

        Returns:
            Dict with enrichment status and comparison data
        """
        try:
            # Import here to avoid circular dependency
            from backend.agents.orchestrator.runner import recall_memory_impl

            # Search memory for similar past queries
            memory_result = await recall_memory_impl(question)

            # If no history found, return gracefully
            if not memory_result.get("success") or not memory_result.get("past_results"):
                return {
                    "enriched": False,
                    "reason": "No historical data found for comparison",
                    "current": current_data
                }

            past_data = memory_result["past_results"]

            # Extract numbers from current and past data for comparison
            current_numbers = self._extract_numbers(current_data)
            past_numbers = self._extract_numbers(past_data.get("result", ""))

            if not current_numbers or not past_numbers:
                return {
                    "enriched": False,
                    "reason": "Could not extract numeric values for comparison",
                    "current": current_data
                }

            # Calculate comparison (use first number found)
            current_val = current_numbers[0]
            past_val = past_numbers[0]
            delta = current_val - past_val

            # Calculate percentage change (avoid division by zero)
            if past_val != 0:
                pct_change = (delta / past_val) * 100
                pct_str = f"{'+' if pct_change > 0 else ''}{pct_change:.1f}%"
            else:
                pct_str = "N/A"

            # Determine trend
            if delta > 0:
                trend = "increasing"
            elif delta < 0:
                trend = "decreasing"
            else:
                trend = "stable"

            return {
                "enriched": True,
                "current": current_val,
                "current_raw": current_data,
                "previous": past_val,
                "previous_date": past_data.get("date", "unknown"),
                "delta": delta,
                "pct_change": pct_str,
                "trend": trend,
                "comparison_text": f"Compared to {past_data.get('date', 'previous check')} ({past_val}), that's {pct_str} ({'+' if delta > 0 else ''}{delta})"
            }

        except Exception as e:
            logger.error(f"EnrichWithHistory skill failed: {str(e)}")
            return {
                "enriched": False,
                "reason": f"Enrichment failed: {str(e)}",
                "current": current_data
            }

    def _extract_numbers(self, text: str) -> list:
        """Extract all numbers from text."""
        # Match integers and floats
        numbers = re.findall(r'-?\d+\.?\d*', str(text))
        return [float(n) for n in numbers if n]
```

### Skills Init (backend/agents/skills/__init__.py)

```python
from backend.agents.skills.base import BaseSkill
from backend.agents.skills.registry import SkillRegistry, get_skill_registry
from backend.agents.skills.summarize import SummarizeSkill
from backend.agents.skills.enrich_with_history import EnrichWithHistorySkill


def initialize_skills():
    """Register all skills at startup."""
    registry = get_skill_registry()
    registry.register(SummarizeSkill())
    registry.register(EnrichWithHistorySkill())


__all__ = ["BaseSkill", "SkillRegistry", "get_skill_registry", "initialize_skills"]
```

---

## Section 4D: Orchestrator (Main Agent)

### Orchestrator Prompt (backend/agents/orchestrator/prompts.py)

```python
ORCHESTRATOR_SYSTEM_PROMPT = """You are an intelligent orchestrator agent that routes user requests to specialized sub-agents and skills.

Available sub-agents:
1. **data_agent**: For SQL database queries and data analysis
   - Use when user asks about data in databases
   - Can query multiple connections and combine results
   - Returns SQL queries and structured data

2. **rag_agent**: For document-based questions
   - Use when user asks about uploaded documents/markdown files
   - Returns answers with source citations
   - Searches Qdrant vector store

3. **recall_memory** (Phase 06 - stub): For retrieving conversation history
   - Use when user asks "what did we discuss before?"
   - Currently returns placeholder (used internally by enrich_with_history)

Available skills:
- **summarize_text**: Summarize long text content
- **enrich_with_history**: Compare current data with past results (call AFTER data_agent)
- (More skills can be added dynamically)

Guidelines:
1. **Understand intent**: Determine if question is about data, documents, or general
2. **Route appropriately**: Choose the right sub-agent or skill
3. **Multi-step enrichment**: For data questions, follow this pattern:
   - Step 1: Call data_agent to get fresh data
   - Step 2: Call enrich_with_history to compare with historical data
   - Step 3: Synthesize final answer with both fresh data and historical context
4. **Graceful degradation**: If enrich_with_history returns enriched=false (no history),
   just present the fresh data without comparison
5. **Stream progress**: Provide status updates during long operations
6. **Handle errors**: If a sub-agent fails, try alternative approaches

Example routing decisions:
- "How many users signed up last month?" → data_agent → enrich_with_history → synthesize
- "What does the documentation say about authentication?" → rag_agent (no enrichment)
- "Summarize the last query results" → summarize_text skill
- "What did we talk about yesterday?" → recall_memory (Phase 06)

Multi-step example for data questions:
User: "How many users we have?"
1. Call data_agent("How many users we have?") → "142 users"
2. Call enrich_with_history(current_data="142 users", question="How many users we have?")
   → {enriched: true, previous: 120, pct_change: "+18.3%", ...}
3. Synthesize: "We have 142 users. Compared to 2 weeks ago (120 users), that's an 18% increase."

You have conversation memory via thread_id - reference past context when helpful."""
```

### Orchestrator Runner (backend/agents/orchestrator/runner.py)

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from backend.agents.orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from backend.agents.data_agent import invoke_data_agent
from backend.agents.rag_agent import invoke_rag_agent
from backend.agents.skills import get_skill_registry
from backend.agents.context import AgentContext
from backend.agents.state import QueryState
from backend.llm.factory import get_llm_provider
from backend.config import settings
from typing import Dict, Any, AsyncGenerator
import json
import logging

logger = logging.getLogger(__name__)


def build_orchestrator_tools(context: AgentContext):
    """
    Build orchestrator tools with sub-agents as tools.

    Each sub-agent is wrapped as a tool that the orchestrator can invoke.
    Context is captured via closure for thread-safety.
    """

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
        Recall past conversation context. Use when user explicitly asks about history.

        NOTE: This is also used internally by enrich_with_history skill.
        The orchestrator can call this directly for user memory queries,
        but for data enrichment, call enrich_with_history instead.

        Args:
            query: What to recall from memory

        Returns:
            JSON string with recalled context (Phase 06 - currently stub)
        """
        result = await recall_memory_impl(query)
        return json.dumps(result)


async def recall_memory_impl(query: str) -> Dict[str, Any]:
    """
    Internal implementation of recall_memory.
    Used by both the recall_memory tool and EnrichWithHistorySkill.

    Returns dict (not JSON string) for internal use.
    """
    # TODO: Implement in Phase 06 with Qdrant vector search
    return {
        "success": False,
        "message": "Memory system not yet implemented (Phase 06)",
        "past_results": None
    }


    # Get skills from registry
    skill_tools = get_skill_registry().to_tools()

    # Combine sub-agent tools + skill tools
    return [data_agent, rag_agent, recall_memory] + skill_tools


async def run_orchestrator(
    user_question: str,
    context: AgentContext
) -> Dict[str, Any]:
    """
    Run orchestrator agent (non-streaming).

    Args:
        user_question: User's natural language question
        context: AgentContext with user_id, available_connections, thread_id

    Returns:
        Dict with success, message, metadata (sub-agent results)
    """
    # Build tools with captured context
    tools = build_orchestrator_tools(context)

    # Get LLM provider
    provider = get_llm_provider(settings.default_llm_provider)

    # Create orchestrator with memory
    memory = MemorySaver()
    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        checkpointer=memory,
        state_modifier=ORCHESTRATOR_SYSTEM_PROMPT
    )

    try:
        # Invoke with thread_id for conversation memory
        config = {"configurable": {"thread_id": context.thread_id or "default"}}

        result = await orchestrator.ainvoke(
            {"messages": [HumanMessage(content=user_question)]},
            config=config
        )

        # Extract final answer and tool results
        messages = result.get("messages", [])

        final_answer = None
        tool_results = []

        for msg in messages:
            # Collect tool results
            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    tool_result = json.loads(msg.content)
                    if isinstance(tool_result, dict) and "success" in tool_result:
                        tool_results.append(tool_result)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Get final AI message
            if hasattr(msg, "type") and msg.type == "ai" and not hasattr(msg, "tool_calls"):
                final_answer = msg.content

        return {
            "success": True,
            "message": final_answer or "Request completed",
            "metadata": {
                "tool_results": tool_results,
                "thread_id": context.thread_id
            }
        }

    except Exception as e:
        logger.error(f"Orchestrator failed: {str(e)}")
        return {
            "success": False,
            "message": f"Orchestrator failed: {str(e)}",
            "metadata": {}
        }


async def stream_orchestrator(
    user_question: str,
    context: AgentContext
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream orchestrator agent responses via SSE.

    Yields events:
    - {"type": "status", "content": "Starting..."}
    - {"type": "tool_call", "content": {"tool": "data_agent", "args": {...}}}
    - {"type": "tool_result", "content": {...}}
    - {"type": "token", "content": "word"}
    - {"type": "done", "thread_id": "..."}
    - {"type": "error", "content": "error message"}

    Args:
        user_question: User's question
        context: AgentContext

    Yields:
        Event dicts for SSE streaming
    """
    tools = build_orchestrator_tools(context)
    provider = get_llm_provider(settings.default_llm_provider)

    memory = MemorySaver()
    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        checkpointer=memory,
        state_modifier=ORCHESTRATOR_SYSTEM_PROMPT
    )

    try:
        yield {"type": "status", "content": "Starting orchestrator..."}

        config = {"configurable": {"thread_id": context.thread_id or "default"}}

        # Stream agent execution
        async for event in orchestrator.astream(
            {"messages": [HumanMessage(content=user_question)]},
            config=config
        ):
            # Parse LangGraph stream events
            if isinstance(event, dict):
                for node_name, node_data in event.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            # Tool calls
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    yield {
                                        "type": "tool_call",
                                        "content": {
                                            "tool": tool_call.get("name"),
                                            "args": tool_call.get("args", {})
                                        }
                                    }

                            # Tool results
                            if hasattr(msg, "content") and isinstance(msg.content, str):
                                try:
                                    result = json.loads(msg.content)
                                    if isinstance(result, dict) and "success" in result:
                                        yield {"type": "tool_result", "content": result}
                                except (json.JSONDecodeError, TypeError):
                                    pass

                            # AI response tokens (simplified - actual streaming would need provider support)
                            if hasattr(msg, "type") and msg.type == "ai" and not hasattr(msg, "tool_calls"):
                                # Stream tokens if available
                                if hasattr(msg, "content"):
                                    yield {"type": "token", "content": msg.content}

        yield {"type": "done", "thread_id": context.thread_id}

    except Exception as e:
        logger.error(f"Orchestrator streaming failed: {str(e)}")
        yield {"type": "error", "content": str(e)}


__all__ = ["run_orchestrator", "stream_orchestrator"]
```

---

## Section 4E: Step Collection (Agent Execution Tracing)

### Step Collector (backend/agents/step_collector.py)

Collects agent execution steps for logging and display:

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time


@dataclass
class StepRecord:
    """
    A single step in the agent execution trace.

    Captures reasoning, tool calls, tool results, and final answers
    for debugging and display in frontend.
    """
    agent_type: str       # "orchestrator" | "data_agent" | "rag_agent" | "skill"
    step_type: str        # "reasoning" | "tool_call" | "tool_result" | "final_answer"
    tool_name: Optional[str] = None
    content: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[int] = None


class StepCollector:
    """
    Collects agent execution steps for logging to database.

    Used by orchestrator to capture the full reasoning chain:
    - What the LLM decided to do (reasoning)
    - What tools were called (tool_call)
    - What results came back (tool_result)
    - The final synthesized answer (final_answer)
    """

    def __init__(self):
        self._steps: List[StepRecord] = []
        self._timer_start: Optional[float] = None

    def start_timer(self):
        """Start timing for next step."""
        self._timer_start = time.monotonic()

    def stop_timer(self) -> Optional[int]:
        """Stop timer and return elapsed milliseconds."""
        if self._timer_start is None:
            return None
        elapsed = int((time.monotonic() - self._timer_start) * 1000)
        self._timer_start = None
        return elapsed

    def add_reasoning(self, agent_type: str, text: str, decision: str = None):
        """
        Record LLM reasoning step.

        Args:
            agent_type: Which agent (orchestrator, data_agent, etc.)
            text: The reasoning text
            decision: Optional decision tag (e.g., "route_to_data_agent")
        """
        content = {"text": text}
        if decision:
            content["decision"] = decision
        self._steps.append(StepRecord(
            agent_type=agent_type,
            step_type="reasoning",
            content=content
        ))

    def add_tool_call(self, agent_type: str, tool_name: str, args: Dict):
        """
        Record tool invocation.

        Args:
            agent_type: Which agent called the tool
            tool_name: Name of the tool
            args: Tool arguments
        """
        self._steps.append(StepRecord(
            agent_type=agent_type,
            step_type="tool_call",
            tool_name=tool_name,
            content={"tool": tool_name, "args": args}
        ))

    def add_tool_result(self, agent_type: str, tool_name: str, result: Dict, duration_ms: int = None):
        """
        Record tool result.

        Args:
            agent_type: Which agent's tool
            tool_name: Name of the tool
            result: Tool result dict
            duration_ms: How long the tool took
        """
        self._steps.append(StepRecord(
            agent_type=agent_type,
            step_type="tool_result",
            tool_name=tool_name,
            content={"tool": tool_name, **result},
            duration_ms=duration_ms
        ))

    def add_final_answer(self, agent_type: str, text: str):
        """
        Record final synthesized answer.

        Args:
            agent_type: Which agent produced the answer
            text: The final answer text
        """
        self._steps.append(StepRecord(
            agent_type=agent_type,
            step_type="final_answer",
            content={"text": text}
        ))

    @property
    def steps(self) -> List[StepRecord]:
        """Get all collected steps."""
        return self._steps

    def clear(self):
        """Clear all steps (for reuse)."""
        self._steps = []
        self._timer_start = None
```

### Integration with Orchestrator (Update to runner.py)

Modify `run_orchestrator()` to collect steps:

```python
async def run_orchestrator(
    user_question: str,
    context: AgentContext
) -> Dict[str, Any]:
    """
    Run orchestrator agent (non-streaming) with step collection.

    Returns dict with steps for persistence to database.
    """
    collector = StepCollector()  # NEW: Create step collector
    tools = build_orchestrator_tools(context)
    provider = get_llm_provider(settings.default_llm_provider)

    memory = MemorySaver()
    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        checkpointer=memory,
        state_modifier=ORCHESTRATOR_SYSTEM_PROMPT
    )

    try:
        config = {"configurable": {"thread_id": context.thread_id or "default"}}

        result = await orchestrator.ainvoke(
            {"messages": [HumanMessage(content=user_question)]},
            config=config
        )

        messages = result.get("messages", [])
        final_answer = None
        tool_results = []

        # NEW: Parse messages and populate collector
        for msg in messages:
            # Tool calls (LLM decided to call a tool)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    # Reasoning leading to tool call
                    if hasattr(msg, "content") and msg.content:
                        collector.add_reasoning("orchestrator", msg.content, tc["name"])
                    # Tool call itself
                    collector.add_tool_call("orchestrator", tc["name"], tc.get("args", {}))

            # Tool results
            elif hasattr(msg, "type") and msg.type == "tool":
                try:
                    result_dict = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    if isinstance(result_dict, dict):
                        collector.add_tool_result("orchestrator", msg.name, result_dict)
                        tool_results.append(result_dict)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Final answer
            elif hasattr(msg, "type") and msg.type == "ai" and not hasattr(msg, "tool_calls"):
                final_answer = msg.content
                collector.add_final_answer("orchestrator", msg.content)

        return {
            "success": True,
            "message": final_answer or "Request completed",
            "metadata": {
                "tool_results": tool_results,
                "thread_id": context.thread_id
            },
            "steps": collector.steps  # NEW: Return steps for persistence
        }

    except Exception as e:
        logger.error(f"Orchestrator failed: {str(e)}")
        return {
            "success": False,
            "message": f"Orchestrator failed: {str(e)}",
            "metadata": {},
            "steps": []
        }
```

Modify `stream_orchestrator()` to collect steps while streaming:

```python
async def stream_orchestrator(
    user_question: str,
    context: AgentContext
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream orchestrator agent responses via SSE with step collection.

    Yields events AND collects steps for later persistence.
    """
    collector = StepCollector()  # NEW: Create step collector
    tools = build_orchestrator_tools(context)
    provider = get_llm_provider(settings.default_llm_provider)

    memory = MemorySaver()
    orchestrator = create_react_agent(
        model=provider.get_langchain_llm(),
        tools=tools,
        checkpointer=memory,
        state_modifier=ORCHESTRATOR_SYSTEM_PROMPT
    )

    try:
        yield {"type": "status", "content": "Starting orchestrator..."}

        config = {"configurable": {"thread_id": context.thread_id or "default"}}

        async for event in orchestrator.astream(
            {"messages": [HumanMessage(content=user_question)]},
            config=config
        ):
            if isinstance(event, dict):
                for node_name, node_data in event.items():
                    if "messages" in node_data:
                        for msg in node_data["messages"]:
                            # Tool calls
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tool_call in msg.tool_calls:
                                    # NEW: Collect step
                                    if hasattr(msg, "content") and msg.content:
                                        collector.add_reasoning("orchestrator", msg.content, tool_call.get("name"))
                                    collector.add_tool_call("orchestrator", tool_call.get("name"), tool_call.get("args", {}))

                                    # Yield SSE event
                                    yield {
                                        "type": "tool_call",
                                        "content": {
                                            "tool": tool_call.get("name"),
                                            "args": tool_call.get("args", {})
                                        }
                                    }

                            # Tool results
                            if hasattr(msg, "content") and isinstance(msg.content, str):
                                try:
                                    result = json.loads(msg.content)
                                    if isinstance(result, dict) and "success" in result:
                                        # NEW: Collect step
                                        collector.add_tool_result("orchestrator", msg.name if hasattr(msg, "name") else "unknown", result)
                                        # Yield SSE event
                                        yield {"type": "tool_result", "content": result}
                                except (json.JSONDecodeError, TypeError):
                                    pass

                            # AI response tokens
                            if hasattr(msg, "type") and msg.type == "ai" and not hasattr(msg, "tool_calls"):
                                if hasattr(msg, "content"):
                                    # NEW: Collect final answer
                                    collector.add_final_answer("orchestrator", msg.content)
                                    # Yield SSE event
                                    yield {"type": "token", "content": msg.content}

        # NEW: Yield steps for persistence
        yield {"type": "done", "thread_id": context.thread_id, "steps": collector.steps}

    except Exception as e:
        logger.error(f"Orchestrator streaming failed: {str(e)}")
        yield {"type": "error", "content": str(e)}
```

---

## Testing & Verification

### Unit Tests (backend/tests/test_data_agent_tools.py)

```python
import pytest
from backend.agents.data_agent.tools import build_data_agent_tools
from backend.agents.context import AgentContext


def test_closure_based_tools():
    """Test that tools capture context via closure."""
    context = AgentContext(user_id="user-123", available_connections=[1])
    tools = build_data_agent_tools(context)

    assert len(tools) == 4
    assert all(callable(tool) for tool in tools)


def test_list_tables_with_context():
    """Test list_tables with captured context."""
    context = AgentContext(user_id="user-123", available_connections=[1])
    tools = build_data_agent_tools(context)
    list_tables_tool = tools[0]

    result = list_tables_tool.invoke({"connection_id": 1})
    assert isinstance(result, list)


def test_authorization_via_context():
    """Test connection authorization through context."""
    context = AgentContext(user_id="user-123", available_connections=[1])
    tools = build_data_agent_tools(context)
    list_tables_tool = tools[0]

    # Should fail for unauthorized connection
    result = list_tables_tool.invoke({"connection_id": 999})
    assert result == []
```

### Integration Test (backend/tests/test_orchestrator.py)

```python
import pytest
from backend.agents.orchestrator import run_orchestrator
from backend.agents.context import AgentContext


@pytest.mark.asyncio
async def test_orchestrator_routes_to_data_agent():
    """Test orchestrator routes data questions to data agent."""
    context = AgentContext(
        user_id="user-123",
        available_connections=[1],
        thread_id="test-thread"
    )

    result = await run_orchestrator(
        user_question="How many users are in the database?",
        context=context
    )

    assert result["success"] is True
    assert "metadata" in result
    # Verify data_agent was called (check tool_results)


@pytest.mark.asyncio
async def test_orchestrator_routes_to_rag_agent():
    """Test orchestrator routes document questions to RAG agent."""
    context = AgentContext(
        user_id="user-123",
        available_connections=[],
        thread_id="test-thread"
    )

    result = await run_orchestrator(
        user_question="What does the documentation say about authentication?",
        context=context
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_orchestrator_thread_isolation():
    """Test that different threads have isolated contexts."""
    context1 = AgentContext(user_id="user-1", available_connections=[1], thread_id="thread-1")
    context2 = AgentContext(user_id="user-2", available_connections=[2], thread_id="thread-2")

    # Run both concurrently - should not interfere
    import asyncio
    results = await asyncio.gather(
        run_orchestrator("Question 1", context1),
        run_orchestrator("Question 2", context2)
    )

    assert len(results) == 2
    assert all(r["success"] for r in results)
```

### Manual Testing

1. **Test Data Agent via Orchestrator**:
   ```python
   context = AgentContext(user_id="user-123", available_connections=[1])
   result = await run_orchestrator(
       user_question="Show me all users",
       context=context
   )
   ```

2. **Test RAG Agent via Orchestrator**:
   ```python
   context = AgentContext(user_id="user-123", available_connections=[])
   result = await run_orchestrator(
       user_question="What are the API endpoints?",
       context=context
   )
   ```

3. **Test Streaming**:
   ```python
   async for event in stream_orchestrator("Count users", context):
       print(event["type"], event["content"])
   ```

## Code Review Checklist

- [ ] AgentContext used for thread-safe operation (no globals)
- [ ] Tools built via closures with captured context
- [ ] Data Agent is stateless (no checkpointer)
- [ ] Orchestrator has memory (MemorySaver checkpointer)
- [ ] Sub-agents wrapped as tools (not subgraphs)
- [ ] Skills framework supports dynamic registration
- [ ] EnrichWithHistorySkill registered and converts to tool
- [ ] Orchestrator prompt guides multi-step: data → enrich → synthesize
- [ ] Enrichment gracefully degrades when no history (returns enriched: false)
- [ ] RAG agent wraps existing langgraph/runner.py
- [ ] Streaming works with SSE event types
- [ ] StepCollector captures reasoning, tool calls, results, final answer
- [ ] run_orchestrator returns steps for persistence
- [ ] stream_orchestrator yields steps in done event
- [ ] Tests verify closure isolation
- [ ] recall_memory stub present (Phase 06)

## Done Criteria

1. AgentContext dataclass created
2. Data Agent tools use closure-based context (no globals)
3. Data Agent invokable as stateless agent
4. RAG Agent wrapper working
5. Skills framework (BaseSkill, SkillRegistry, SummarizeSkill)
6. Orchestrator routes to sub-agents via tools
7. Orchestrator has conversation memory (thread_id)
8. Streaming works with SSE events
9. Tests verify thread-safety and isolation
10. No global state for user/connection data
11. EnrichWithHistorySkill implemented with graceful degradation
12. Orchestrator prompt guides enrichment after data queries
13. StepCollector captures full execution trace
14. Steps returned from orchestrator for database persistence

## Rollback Plan

If this phase fails:
1. Remove backend/agents/ directory
2. No API changes to rollback (self-contained module)

## Architecture Comparison

**This Implementation** (Single-channel):
```
Nuxt Frontend → REST/SSE → Orchestrator → Sub-Agents (data, rag, memory)
                                        → Skills (summarize, ...)
```

**OpenClaw Pattern** (Multi-channel - NOT implemented):
```
13+ channels → WebSocket Gateway → Workspace Agents → Sub-Agents
```

**Key Difference**: We use a single communication channel (Nuxt frontend) instead of multi-channel gateway.
