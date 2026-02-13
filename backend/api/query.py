from fastapi import Query, HTTPException, Depends
from typing import Optional
from backend.models.requests import QueryRequest
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.responses import QueryResponse, QueryResult
from backend.embedder.openai import embed_text
from backend.vectordb.pinecone import query_vectors
import logging

logger = logging.getLogger(__name__)

async def query(
    request: QueryRequest,
    current_user: User = Depends(get_current_user)
) -> QueryResponse:
    """Vector similarity search."""
    # Embed the query
    query_embedding = await embed_text(request.query)

    # Search Pinecone
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=request.namespace,
        top_k=request.top_k,
        filter=request.filter
    )

    # Format results
    formatted_results = []
    for r in results:
        formatted_results.append(QueryResult(
            id=r["id"],
            score=round(r["score"], 4),
            source=r["metadata"].get("source", "unknown"),
            chunk_index=r["metadata"].get("chunk_index", 0),
            text=r["metadata"].get("text", ""),
            created_at=r["metadata"].get("created_at")
        ))

    return QueryResponse(
        query=request.query,
        results=formatted_results,
        namespace=request.namespace,
        total_results=len(formatted_results)
    )

async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    namespace: str = Query("default", description="Namespace to search"),
    limit: int = Query(5, ge=1, le=100, description="Max results"),
    current_user: User = Depends(get_current_user)
) -> QueryResponse:
    """Simple search via query parameters."""
    request = QueryRequest(query=q, namespace=namespace, top_k=limit)
    return await query(request, current_user)
