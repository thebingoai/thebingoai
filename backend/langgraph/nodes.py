from langchain_core.messages import HumanMessage, AIMessage
from backend.embedder.openai import embed_text
from backend.vectordb.pinecone import query_vectors
from backend.langgraph.state import ConversationState, ContextSource
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


async def retrieve_context(state: ConversationState) -> ConversationState:
    """
    Retrieve relevant documents from Pinecone.

    Node: retrieve_context
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

        sources.append(ContextSource(
            source=source,
            chunk_index=chunk_idx,
            score=round(score, 4)
        ))

    has_context = len(context) > 0 and context[0]["score"] > 0.5

    logger.info(f"Retrieved {len(context)} chunks, has_context={has_context}")

    return {
        **state,
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
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver

    # Create graph with state schema
    workflow = StateGraph(ConversationState)

    # Add nodes
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_response", generate_response)

    # Set entry point
    workflow.set_entry_point("retrieve_context")

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
