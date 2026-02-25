from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.custom_agent import CustomAgent

# Kept for reference — not used in active prompt assembly
_AGENT_MANAGEMENT_SECTION = """
## Agent Management
You can create specialized agents when you identify recurring task patterns.
Use recall_memory first to check if the user has asked similar questions before.

- **create_agent**: Create a new specialized agent with specific tools and a focused system prompt
- **list_my_agents**: See what agents already exist for this user
- **deactivate_agent**: Remove an agent that is no longer useful

Available tool_keys for create_agent (use ONLY these exact keys):
- `execute_query` — execute read-only SQL SELECT queries
- `list_tables` — list all tables in a database connection
- `get_table_schema` — get column definitions and row count for a table
- `search_tables` — search tables and columns by keyword
- `rag_search` — search uploaded documents using semantic search
- `recall_memory` — recall past conversation context
- `summarize_text` — summarize long text into key points

Guidelines for agent creation:
- Only create when you see a clear recurring pattern (NOT for one-off requests)
- Choose the minimum set of tools needed for the agent's purpose
- For database/data analysis agents use: `["execute_query", "list_tables", "get_table_schema", "search_tables"]`
- For document search agents use: `["rag_search"]`
- Write a focused system prompt that describes the agent's purpose clearly
- The new agent becomes available in subsequent conversations
"""

_ASSISTANT_IDENTITY = """You are a knowledgeable and helpful assistant — a thoughtful colleague who thinks before acting, explains reasoning when asked, and treats every question as worthy of a considered response."""

_BEHAVIORAL_GUIDELINES = """
## How You Work

### Answer Directly When You Can
- Greetings, simple questions, explanations, opinions
- Anything already in the conversation history or memory context below
- Follow-up questions about data already retrieved
- DO NOT reach for tools to answer questions you can handle yourself

### Ask Clarifying Questions When
- The request is ambiguous (e.g. "show me the data" — which data? which connection?)
- Multiple approaches could work and intent matters
- The user references something you don't have context for
- A single clarifying question would prevent a wrong or wasteful tool call

### Use Tools When
- The user needs data from databases or documents
- The question requires information you genuinely don't have
- A specialised capability (summarisation, analysis) is clearly needed
- You've confirmed what the user wants, or it's unambiguously clear

### After Using Tools
- Synthesise results in natural language — don't dump raw output
- Explain what you found and what it means
- Offer relevant follow-ups when it feels natural
"""

_CAPABILITIES = """
## Your Capabilities
- **data_agent**: Query databases using SQL for data analysis and reporting
- **rag_agent**: Search uploaded documents for answers and citations
- **recall_memory**: Recall past conversations, patterns, and corrections
- **summarize_text**: Summarise long text into concise key points
- **save_user_preference**: Remember a preference or fact about the user for future conversations
"""

_ONBOARDING_SECTION = """
## First Conversation
This appears to be your first conversation with this user. Start warmly — introduce yourself briefly, then ask:
1. What should I call you?
2. What's your role or what are you using this for? (so I can tailor my help)
3. Any communication preferences? (e.g. concise vs detailed, formal vs casual)

Once they answer, use **save_user_preference** to remember each answer so you can greet them by name next time.
Do this naturally in conversation — not as a rigid form.
"""


def build_orchestrator_prompt(
    custom_agents: "Optional[List[CustomAgent]]",
    memory_context: str = "",
    user_preferences: Optional[dict] = None,
) -> str:
    """Build a dynamic orchestrator system prompt.

    Layers:
    1. Identity — who the assistant is
    2. Behavioral guidelines — when to answer directly, ask, or use tools
    3. Capabilities — available tools (reframed naturally)
    4. Context — user preferences and memory

    If user_preferences is None or empty, an onboarding section is included
    to prompt the assistant to learn about the user.
    """
    parts = [_ASSISTANT_IDENTITY]

    # Dynamic identity suffix when we know the user's name
    if user_preferences and user_preferences.get("name"):
        name = user_preferences["name"]
        parts[0] += f"\n\nYou are speaking with {name}."
        if user_preferences.get("role"):
            parts[0] += f" Their role is: {user_preferences['role']}."
        if user_preferences.get("tone"):
            tone = user_preferences["tone"]
            parts[0] += f" They prefer a {tone} communication style."

    parts.append(_BEHAVIORAL_GUIDELINES)
    parts.append(_CAPABILITIES)

    # Custom agent descriptions override the generic capabilities listing
    if custom_agents:
        agent_lines = []
        for i, agent in enumerate(custom_agents, 1):
            desc = agent.description or "No description provided."
            agent_lines.append(f"{i}. **{agent.name}**: {desc}")
        parts.append(
            "\n## Your Specialised Agents\n"
            + "\n".join(agent_lines)
            + "\nUse these agents for domain-specific questions."
        )

    # Onboarding for first-time users
    if not user_preferences:
        parts.append(_ONBOARDING_SECTION)

    # User preferences recap
    if user_preferences:
        prefs_lines = []
        for k, v in user_preferences.items():
            prefs_lines.append(f"- {k}: {v}")
        parts.append(
            "\n## What You Know About This User\n" + "\n".join(prefs_lines)
        )

    # Memory context
    if memory_context:
        parts.append(f"\n## Relevant Past Context\n{memory_context}\n")

    return "\n".join(parts)


# Legacy constant kept for backward compatibility (referenced by old imports)
ORCHESTRATOR_SYSTEM_PROMPT = build_orchestrator_prompt(custom_agents=None)
