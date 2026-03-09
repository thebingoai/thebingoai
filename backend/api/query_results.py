"""
API endpoint for fetching cached query results.

Clients use this as a REST fallback when the WebSocket query.result event
was missed, or to re-fetch a result by its reference ID.
"""
from fastapi import APIRouter, Depends, HTTPException
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.services.query_result_store import get_query_result

router = APIRouter(prefix="/query-results", tags=["query-results"])


@router.get("/{result_ref}")
async def fetch_query_result(
    result_ref: str,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve a cached query result by its reference ID.

    Results are stored for 1 hour after execution. Returns 404 if expired
    or if the result does not belong to the authenticated user.
    """
    data = get_query_result(result_ref, str(current_user.id))
    if data is None:
        raise HTTPException(status_code=404, detail="Query result not found or expired")
    return data
