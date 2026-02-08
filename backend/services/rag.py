from typing import Optional, AsyncGenerator, Union
from backend.vectordb.pinecone import query_vectors
from backend.embedder.openai import embed_text
from backend.llm.factory import get_provider
from backend.prompts import SYSTEM_PROMPT
import logging

logger = logging.getLogger(__name__)

async def ask_with_context(
    question: str,
    namespace: str = "default",
    top_k: int = 5,
    provider: str = "openai",
    model: Optional[str] = None,
    temperature: float = 0.7,
    stream: bool = False
) -> Union[dict, tuple[AsyncGenerator[str, None], list[dict]]]:
    """
    RAG: Retrieve relevant context and generate answer.

    Args:
        question: User's question
        namespace: Namespace to search
        top_k: Number of context chunks to retrieve
        provider: LLM provider to use
        model: Optional model override
        temperature: Generation temperature
        stream: Whether to stream response

    Returns:
        If stream=False: {"answer": str, "sources": list}
        If stream=True: (AsyncGenerator, sources)
    """
    logger.info(f"RAG query: {question[:50]}... (namespace={namespace}, provider={provider})")

    # 1. Embed the question
    query_embedding = await embed_text(question)

    # 2. Retrieve relevant chunks
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=top_k
    )

    if not results:
        logger.warning(f"No results found for query in namespace {namespace}")

    # 3. Build context from results
    context_parts = []
    sources = []

    for r in results:
        source = r["metadata"].get("source", "unknown")
        chunk_idx = r["metadata"].get("chunk_index", 0)
        text = r["metadata"].get("text", "")

        context_parts.append(f"[Source: {source}, Section {chunk_idx}]\n{text}")
        sources.append({
            "source": source,
            "chunk_index": chunk_idx,
            "score": round(r["score"], 4)
        })

    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."

    # 4. Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": question}
    ]

    # 5. Get LLM response
    llm = get_provider(provider, model)

    if stream:
        async def stream_with_context():
            async for token in llm.chat_stream(messages, temperature=temperature):
                yield token

        return stream_with_context(), sources
    else:
        answer = await llm.chat(messages, temperature=temperature)
        return {"answer": answer, "sources": sources}


async def get_context_only(
    question: str,
    namespace: str = "default",
    top_k: int = 5
) -> list[dict]:
    """
    Retrieve context without generating an answer.
    Useful for debugging or when client wants to handle LLM separately.
    """
    query_embedding = await embed_text(question)

    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=top_k
    )

    return [
        {
            "source": r["metadata"].get("source", "unknown"),
            "chunk_index": r["metadata"].get("chunk_index", 0),
            "text": r["metadata"].get("text", ""),
            "score": round(r["score"], 4)
        }
        for r in results
    ]
