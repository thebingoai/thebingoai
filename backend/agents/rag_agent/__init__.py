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
