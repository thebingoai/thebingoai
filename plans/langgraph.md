# LangGraph RAG Workflow

Complete implementation of the LangGraph-based RAG workflow with conversation memory and conditional routing.

---

## Overview

LangGraph provides stateful, graph-based workflows for the RAG chatbot with:
- **Conversation memory** via thread_id
- **Conditional routing** based on context availability
- **Streaming support** for real-time responses

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LangGraph RAG Workflow                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│    User Question                                                    │
│         │                                                           │
│         ▼                                                           │
│   ┌──────────┐                                                      │
│   │ RETRIEVE │ ── Embed question ──► Pinecone search               │
│   └────┬─────┘                                                      │
│        │                                                            │
│        ▼                                                            │
│   ┌──────────┐      has_context?                                   │
│   │CONDITIONAL│ ──────────────────┐                                 │
│   └────┬─────┘                    │                                 │
│        │ Yes                      │ No                              │
│        ▼                          ▼                                 │
│   ┌──────────┐             ┌─────────────┐                         │
│   │ GENERATE │             │ GENERATE    │                         │
│   │ w/context│             │ no-context  │                         │
│   └────┬─────┘             │ fallback    │                         │
│        │                   └──────┬──────┘                         │
│        ▼                          │                                 │
│   ┌──────────┐                    │                                 │
│   │  Memory  │ ◄──────────────────┘                                 │
│   │Checkpoint│                                                      │
│   └────┬─────┘                                                      │
│        │                                                            │
│        ▼                                                            │
│     Response                                                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Thread Memory:
  thread_id="abc123" → [Human: Q1, AI: A1, Human: Q2, AI: A2, ...]
```

---

## Requirements

Add to `backend/requirements.txt`:

```
# LangGraph & LangChain
langgraph==0.2.0
langchain-core==0.3.0
langchain-openai==0.2.0
langchain-anthropic==0.2.0
langchain-community==0.3.0
```

---

## 1. Graph State

### Create `backend/graph/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/graph/state.py`

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class GraphState(TypedDict):
    """State for the RAG conversation graph."""

    # Conversation messages (with automatic history management)
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # Current question being processed
    question: str

    # Retrieved context chunks
    context: list[dict]

    # Namespace for vector search
    namespace: str

    # Selected LLM provider
    provider: str

    # Model override (optional)
    model: str | None

    # Whether context was found
    has_context: bool

    # Final answer (set by generate node)
    answer: str | None

    # Sources used in the answer
    sources: list[dict]
```

---

## 2. Graph Nodes

### Create `backend/graph/nodes.py`

```python
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend.embedder.openai import embed_text
from backend.vectordb.pinecone import query_vectors
from backend.graph.state import GraphState
from backend.llm.factory import get_provider
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the user's personal notes and documents.

Use the provided context to answer the question. If the context contains relevant information, cite it specifically. If the context doesn't contain enough information to fully answer the question, say so clearly and provide what help you can.

Be concise but thorough. Use the same terminology found in the user's notes when possible.

Context from user's documents:
---
{context}
---

Remember: Only use information from the context above. If you're not sure about something, say so."""

NO_CONTEXT_PROMPT = """You are a helpful assistant. The user asked a question but no relevant documents were found in their indexed files.

Let them know politely that you couldn't find relevant information in their notes, and offer to help if they:
1. Index more files using @folder
2. Rephrase their question
3. Ask about something else

Be helpful and conversational."""


async def retrieve(state: GraphState) -> GraphState:
    """
    Retrieve relevant documents from Pinecone.

    Node: retrieve
    """
    question = state["question"]
    namespace = state["namespace"]

    logger.info(f"Retrieving context for: {question[:50]}...")

    # Embed the question
    query_embedding = await embed_text(question)

    # Search Pinecone
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=5
    )

    # Extract context and sources
    context = []
    sources = []

    for r in results:
        source = r["metadata"].get("source", "unknown")
        chunk_idx = r["metadata"].get("chunk_index", 0)
        text = r["metadata"].get("text", "")
        score = r["score"]

        context.append({
            "source": source,
            "chunk_index": chunk_idx,
            "text": text,
            "score": score
        })

        sources.append({
            "source": source,
            "chunk_index": chunk_idx,
            "score": round(score, 4)
        })

    has_context = len(context) > 0 and context[0]["score"] > 0.5

    logger.info(f"Retrieved {len(context)} chunks, has_context={has_context}")

    return {
        **state,
        "context": context,
        "sources": sources,
        "has_context": has_context
    }


async def generate(state: GraphState) -> GraphState:
    """
    Generate answer using LLM with retrieved context.

    Node: generate
    """
    question = state["question"]
    context = state["context"]
    provider = state["provider"]
    model = state.get("model")
    messages = list(state["messages"])

    logger.info(f"Generating answer with {provider}")

    # Build context string
    if context:
        context_str = "\n\n---\n\n".join([
            f"[Source: {c['source']}, Section {c['chunk_index']}]\n{c['text']}"
            for c in context
        ])
        system_content = SYSTEM_PROMPT.format(context=context_str)
    else:
        system_content = NO_CONTEXT_PROMPT

    # Get LLM provider
    llm = get_provider(provider, model)

    # Build messages for LLM
    llm_messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question}
    ]

    # Include recent conversation history for context
    for msg in messages[-6:]:  # Last 3 exchanges
        if isinstance(msg, HumanMessage):
            llm_messages.insert(-1, {"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            llm_messages.insert(-1, {"role": "assistant", "content": msg.content})

    # Generate response
    answer = await llm.chat(llm_messages, temperature=0.7)

    # Add to message history
    new_messages = [
        HumanMessage(content=question),
        AIMessage(content=answer)
    ]

    return {
        **state,
        "answer": answer,
        "messages": new_messages  # add_messages will append
    }


async def generate_stream(state: GraphState):
    """
    Generate answer with streaming.

    Node: generate_stream (alternative to generate)
    """
    question = state["question"]
    context = state["context"]
    provider = state["provider"]
    model = state.get("model")

    # Build context string
    if context:
        context_str = "\n\n---\n\n".join([
            f"[Source: {c['source']}, Section {c['chunk_index']}]\n{c['text']}"
            for c in context
        ])
        system_content = SYSTEM_PROMPT.format(context=context_str)
    else:
        system_content = NO_CONTEXT_PROMPT

    llm = get_provider(provider, model)

    llm_messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question}
    ]

    # Yield tokens
    full_response = ""
    async for token in llm.chat_stream(llm_messages, temperature=0.7):
        full_response += token
        yield {"token": token}

    # Final state update
    yield {
        "answer": full_response,
        "messages": [
            HumanMessage(content=question),
            AIMessage(content=full_response)
        ]
    }


def should_generate(state: GraphState) -> str:
    """
    Conditional edge: decide whether to generate or handle no-context.

    Returns:
        "generate" if context found
        "no_context" if no relevant context
    """
    if state.get("has_context", False):
        return "generate"
    else:
        return "no_context"
```

---

## 3. Workflow Graph

### Create `backend/graph/workflow.py`

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from backend.graph.state import GraphState
from backend.graph.nodes import retrieve, generate, should_generate
import logging

logger = logging.getLogger(__name__)

def create_rag_graph() -> StateGraph:
    """
    Create the RAG workflow graph.

    Graph structure:
        START → retrieve → [conditional] → generate → END
                              ↓
                          no_context → generate → END
    """
    # Create graph with state schema
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("generate", generate)

    # Set entry point
    workflow.set_entry_point("retrieve")

    # Add conditional edge after retrieve
    workflow.add_conditional_edges(
        "retrieve",
        should_generate,
        {
            "generate": "generate",
            "no_context": "generate"  # Still generate, but with different prompt
        }
    )

    # Generate always ends
    workflow.add_edge("generate", END)

    return workflow


# Memory saver for conversation persistence
memory = MemorySaver()

def get_compiled_graph():
    """Get compiled graph with memory checkpointing."""
    workflow = create_rag_graph()
    return workflow.compile(checkpointer=memory)


# Singleton compiled graph
_graph = None

def get_graph():
    """Get or create the compiled graph."""
    global _graph
    if _graph is None:
        _graph = get_compiled_graph()
    return _graph
```

---

## 4. Graph Runner

### Create `backend/graph/runner.py`

```python
from typing import AsyncGenerator, Optional
from langchain_core.messages import HumanMessage
from backend.graph.workflow import get_graph
from backend.graph.state import GraphState
import uuid
import logging

logger = logging.getLogger(__name__)


async def run_rag_query(
    question: str,
    namespace: str = "default",
    provider: str = "openai",
    model: Optional[str] = None,
    thread_id: Optional[str] = None,
    stream: bool = False
) -> dict | AsyncGenerator[dict, None]:
    """
    Run a RAG query through the LangGraph workflow.

    Args:
        question: User's question
        namespace: Pinecone namespace
        provider: LLM provider
        model: Optional model override
        thread_id: Conversation thread ID (for memory)
        stream: Whether to stream the response

    Returns:
        If stream=False: {"answer": str, "sources": list, "thread_id": str}
        If stream=True: AsyncGenerator yielding tokens
    """
    graph = get_graph()

    # Use existing thread or create new
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # Initial state
    initial_state: GraphState = {
        "messages": [],
        "question": question,
        "context": [],
        "namespace": namespace,
        "provider": provider,
        "model": model,
        "has_context": False,
        "answer": None,
        "sources": []
    }

    logger.info(f"Running RAG query (thread={thread_id[:8]}...)")

    if stream:
        return _stream_rag_query(graph, initial_state, config, thread_id)
    else:
        # Run graph to completion
        final_state = await graph.ainvoke(initial_state, config)

        return {
            "answer": final_state["answer"],
            "sources": final_state["sources"],
            "thread_id": thread_id,
            "has_context": final_state["has_context"]
        }


async def _stream_rag_query(graph, initial_state, config, thread_id):
    """Stream tokens from the graph execution."""

    # First, run retrieve node
    retrieve_state = await graph.ainvoke(
        initial_state,
        config,
        interrupt_before=["generate"]
    )

    # Yield sources first
    yield {
        "type": "sources",
        "sources": retrieve_state["sources"],
        "has_context": retrieve_state["has_context"]
    }

    # Stream generate node
    async for event in graph.astream_events(
        retrieve_state,
        config,
        version="v2"
    ):
        if event["event"] == "on_chat_model_stream":
            token = event["data"]["chunk"].content
            if token:
                yield {"type": "token", "token": token}

    # Final event
    yield {"type": "done", "thread_id": thread_id}


async def get_conversation_history(thread_id: str) -> list[dict]:
    """Get conversation history for a thread."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = await graph.aget_state(config)
        messages = state.values.get("messages", [])

        return [
            {
                "role": "user" if isinstance(m, HumanMessage) else "assistant",
                "content": m.content
            }
            for m in messages
        ]
    except Exception:
        return []


async def clear_conversation(thread_id: str) -> bool:
    """Clear conversation history for a thread."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        await graph.aupdate_state(config, {"messages": []})
        return True
    except Exception:
        return False
```

---

## 5. LLM Provider Integration

For the LangGraph workflow, ensure the LLM providers are set up properly.

### Create `backend/llm/__init__.py`

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Send messages and get response."""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens."""
        pass

# Import providers for convenient access
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.llm.factory import get_provider

__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "get_provider"
]
```

### Create `backend/llm/factory.py`

```python
from backend.llm import LLMProvider
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.config import settings

def get_provider(
    provider: str = "openai",
    model: str | None = None
) -> LLMProvider:
    """
    Factory function to get LLM provider.

    Args:
        provider: "openai", "anthropic", or "ollama"
        model: Optional model override

    Returns:
        LLMProvider instance
    """
    if provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=model or "gpt-4o"
        )
    elif provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=model or "claude-sonnet-4-20250514"
        )
    elif provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=model or "llama3"
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

---

## 6. CLI Thread Management

Update the TUI to use thread_id for conversation memory.

### In `cli/tui/app.py`

```python
class ChatApp(App):
    def __init__(self, backend_url: str, provider: str = "openai"):
        super().__init__()
        self.backend_url = backend_url
        self.provider = provider
        self.current_namespace = None
        self.thread_id = None  # LangGraph thread for memory
        # ... rest of init

    async def _ask_with_rag(self, question: str) -> None:
        """Send question to backend using LangGraph."""
        from cli.api.client import BackendClient

        log = self.query_one("#messages", RichLog)
        log.write("\n[bold green]🤖[/bold green] [dim]Thinking...[/dim]")

        async with BackendClient(self.backend_url) as client:
            # Stream response
            full_response = ""
            async for event in client.ask_stream(
                question=question,
                namespace=self.current_namespace,
                provider=self.provider,
                thread_id=self.thread_id  # Continue conversation
            ):
                if "sources" in event:
                    # Store sources for display
                    self._current_sources = event["sources"]
                elif "token" in event:
                    full_response += event["token"]
                    # Update display (simplified)
                elif "thread_id" in event:
                    self.thread_id = event["thread_id"]

            log.write(f"[bold green]🤖[/bold green] {full_response}")

            # Show sources
            if self._current_sources:
                sources_str = ", ".join([
                    f"{s['source']}#{s['chunk_index']}"
                    for s in self._current_sources[:3]
                ])
                log.write(f"[dim]Sources: {sources_str}[/dim]")

    def action_clear_history(self) -> None:
        """Clear conversation history and start fresh."""
        self.thread_id = None
        log = self.query_one("#messages", RichLog)
        log.write("[dim]Conversation history cleared.[/dim]")
```

---

## Summary Checklist

After implementing LangGraph components, verify:

- [ ] `backend/graph/state.py` - GraphState TypedDict with messages, question, context, etc.
- [ ] `backend/graph/nodes.py` - retrieve and generate nodes with prompts
- [ ] `backend/graph/workflow.py` - StateGraph with conditional edges
- [ ] `backend/graph/runner.py` - run_rag_query with thread_id support
- [ ] `backend/llm/__init__.py` - LLMProvider ABC with __all__ exports
- [ ] `backend/llm/factory.py` - get_provider factory function
- [ ] Thread management endpoints work (`GET/DELETE /api/conversation/{thread_id}`)
- [ ] Streaming via SSE works correctly
- [ ] Conversation memory persists across queries with same thread_id

---

## Related Files

- [models.md](./models.md) - AskRequest with thread_id field
- [backend-api.md](./backend-api.md) - Chat endpoint using the runner
- [backend-services.md](./backend-services.md) - Simple RAG service (non-LangGraph)
- [phase-3-chat-rag.md](./phase-3-chat-rag.md) - Full LLM provider implementations
