from langchain_core.messages import HumanMessage, AIMessage
from backend.embedder.openai import embed_text
from backend.vectordb.qdrant import query_vectors
from backend.langgraph.state import ConversationState, ContextSource
from backend.llm.factory import get_provider
from backend.prompts import SYSTEM_PROMPT, NO_CONTEXT_PROMPT
from backend.config import settings
import logging

logger = logging.getLogger(__name__)


async def retrieve_context(state: ConversationState) -> ConversationState:
    """
    Retrieve relevant documents from Qdrant.

    Node: retrieve_context
    """
    question = state["question"]
    namespace = state["namespace"]
    top_k = state.get("top_k", settings.rag_default_top_k)

    logger.info(f"Retrieving context for: {question[:50]}...")

    # Embed the question
    query_embedding = await embed_text(question)

    # Search vectors
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=top_k
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

        sources.append(ContextSource(
            source=source,
            chunk_index=chunk_idx,
            score=round(score, 4)
        ))

    has_context = len(context) > 0 and context[0]["score"] > settings.rag_context_score_threshold

    logger.info(f"Retrieved {len(context)} chunks, has_context={has_context}")

    # Return only modified fields - LangGraph merges automatically
    return {
        "context": context,
        "sources": sources,
        "has_context": has_context
    }


async def generate_response(state: ConversationState) -> ConversationState:
    """
    Generate answer using LLM with retrieved context.

    Node: generate_response
    """
    question = state["question"]
    context = state["context"]
    provider = state["provider"]
    model = state.get("model")
    temperature = state.get("temperature", settings.default_llm_temperature)
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
    history_limit = settings.rag_conversation_history_messages
    for msg in messages[-history_limit:]:
        if isinstance(msg, HumanMessage):
            llm_messages.insert(-1, {"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            llm_messages.insert(-1, {"role": "assistant", "content": msg.content})

    # Generate response
    answer = await llm.chat(llm_messages, temperature=temperature)

    # Add to message history
    new_messages = [
        HumanMessage(content=question),
        AIMessage(content=answer)
    ]

    # Return only modified fields - LangGraph merges automatically
    # add_messages reducer will append new messages to existing history
    return {
        "answer": answer,
        "messages": new_messages
    }


def should_generate(state: ConversationState) -> str:
    """
    Conditional edge: decide whether to generate with context or without.

    Returns:
        "generate" if context found
        "no_context" if no relevant context
    """
    if state.get("has_context", False):
        return "generate"
    else:
        return "no_context"


def create_rag_graph():
    """
    Create the RAG workflow graph.

    Graph structure:
        START → retrieve_context → [conditional] → generate_response → END
                                      ↓
                                  no_context → generate_response → END
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver

    # Create graph with state schema
    workflow = StateGraph(ConversationState)

    # Add nodes
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_response", generate_response)

    # Set entry point
    workflow.add_edge(START, "retrieve_context")

    # Add conditional edge after retrieve
    workflow.add_conditional_edges(
        "retrieve_context",
        should_generate,
        {
            "generate": "generate_response",
            "no_context": "generate_response"  # Still generate, but with different prompt
        }
    )

    # Generate always ends
    workflow.add_edge("generate_response", END)

    # Compile with memory checkpointing
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)
