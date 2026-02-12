# Phase 07: Token Usage Tracking

## Objective

Implement token usage tracking service and API for monitoring LLM costs per user, with tracking for chat, memory generation, and query operations.

## Prerequisites

- Phase 02: Authentication (User model, auth)

## Files to Create

### Services
- `backend/services/token_tracking_service.py` - Token tracking logic

### API
- `backend/api/usage.py` - Usage analytics endpoints
- `backend/schemas/usage.py` - Usage schemas

### Tests
- `backend/tests/test_token_tracking.py` - Unit tests

## Files to Modify

- `backend/api/routes.py` - Register usage routes
- `backend/api/chat.py` - Add token tracking to chat endpoint
- `backend/memory/generator.py` - Add token tracking to memory generation
- `backend/agents/query_agent/runner.py` - Track tokens in query agent

## Implementation Details

### 1. Token Tracking Service (backend/services/token_tracking_service.py)

```python
from sqlalchemy.orm import Session
from backend.models.token_usage import TokenUsage, OperationType
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Token pricing (per 1M tokens) - update with actual pricing
TOKEN_PRICING = {
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0}
}

class TokenTrackingService:
    """Service for tracking token usage and calculating costs."""

    @staticmethod
    def calculate_cost(
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """
        Calculate cost based on token usage and model.

        Args:
            model: Model name
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = TOKEN_PRICING.get(model, {"input": 0.0, "output": 0.0})

        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    @staticmethod
    def track_usage(
        db: Session,
        user_id: str,
        operation: OperationType,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> TokenUsage:
        """
        Track token usage for an operation.

        Args:
            db: Database session
            user_id: User ID
            operation: Operation type (chat, memory_generation, etc.)
            model: Model name
            prompt_tokens: Input tokens
            completion_tokens: Output tokens

        Returns:
            TokenUsage record
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = TokenTrackingService.calculate_cost(model, prompt_tokens, completion_tokens)

        usage = TokenUsage(
            user_id=user_id,
            operation=operation,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost
        )

        db.add(usage)
        db.commit()
        db.refresh(usage)

        return usage

    @staticmethod
    def get_user_usage_summary(
        db: Session,
        user_id: str,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Get usage summary for a user.

        Args:
            db: Database session
            user_id: User ID
            start_date: Start date for filtering (default: 30 days ago)
            end_date: End date for filtering (default: now)

        Returns:
            Usage summary dictionary
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        # Query usage records
        records = db.query(TokenUsage).filter(
            TokenUsage.user_id == user_id,
            TokenUsage.timestamp >= start_date,
            TokenUsage.timestamp <= end_date
        ).all()

        # Calculate totals
        total_tokens = sum(r.total_tokens for r in records)
        total_cost = sum(r.cost for r in records)
        total_operations = len(records)

        # Group by operation type
        by_operation = {}
        for op_type in OperationType:
            op_records = [r for r in records if r.operation == op_type]
            by_operation[op_type.value] = {
                "count": len(op_records),
                "tokens": sum(r.total_tokens for r in op_records),
                "cost": sum(r.cost for r in op_records)
            }

        return {
            "user_id": user_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "totals": {
                "operations": total_operations,
                "tokens": total_tokens,
                "cost": round(total_cost, 4)
            },
            "by_operation": by_operation
        }

    @staticmethod
    def get_daily_usage(
        db: Session,
        user_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get daily usage breakdown.

        Args:
            db: Database session
            user_id: User ID
            days: Number of days to retrieve

        Returns:
            List of daily usage dictionaries
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        records = db.query(TokenUsage).filter(
            TokenUsage.user_id == user_id,
            TokenUsage.timestamp >= start_date
        ).all()

        # Group by day
        daily_usage = {}
        for record in records:
            date_key = record.timestamp.date().isoformat()

            if date_key not in daily_usage:
                daily_usage[date_key] = {
                    "date": date_key,
                    "tokens": 0,
                    "cost": 0.0,
                    "operations": 0
                }

            daily_usage[date_key]["tokens"] += record.total_tokens
            daily_usage[date_key]["cost"] += record.cost
            daily_usage[date_key]["operations"] += 1

        # Convert to sorted list
        return sorted(daily_usage.values(), key=lambda x: x["date"])
```

### 2. Usage API (backend/api/usage.py)

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.usage import UsageSummaryResponse, DailyUsageResponse
from backend.services.token_tracking_service import TokenTrackingService
from datetime import datetime, timedelta

router = APIRouter(prefix="/usage", tags=["usage"])

@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to summarize"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get token usage summary for current user.

    - **days**: Number of days to include in summary (default: 30)
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    summary = TokenTrackingService.get_user_usage_summary(
        db, current_user.id, start_date, end_date
    )

    return summary

@router.get("/daily", response_model=DailyUsageResponse)
async def get_daily_usage(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to retrieve"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily token usage breakdown.

    - **days**: Number of days to retrieve (default: 30)
    """
    daily_usage = TokenTrackingService.get_daily_usage(db, current_user.id, days)

    return DailyUsageResponse(daily_usage=daily_usage)
```

### 3. Usage Schemas (backend/schemas/usage.py)

```python
from pydantic import BaseModel
from typing import Dict, Any, List

class UsageSummaryResponse(BaseModel):
    user_id: str
    period: Dict[str, str]  # {start, end}
    totals: Dict[str, Any]  # {operations, tokens, cost}
    by_operation: Dict[str, Dict[str, Any]]  # {operation_name: {count, tokens, cost}}

class DailyUsageEntry(BaseModel):
    date: str
    tokens: int
    cost: float
    operations: int

class DailyUsageResponse(BaseModel):
    daily_usage: List[DailyUsageEntry]
```

### 4. Update Chat API (backend/api/chat.py)

Add token tracking after query agent execution:

```python
from backend.services.token_tracking_service import TokenTrackingService
from backend.models.token_usage import OperationType

@router.post("", response_model=ChatResponse)
async def chat(...):
    # ... existing code ...

    # Run query agent
    result = await run_query_agent(...)

    # Track token usage (get from LLM provider response)
    TokenTrackingService.track_usage(
        db=db,
        user_id=current_user.id,
        operation=OperationType.CHAT,
        model=settings.default_llm_model,
        prompt_tokens=result.get("prompt_tokens", 0),
        completion_tokens=result.get("completion_tokens", 0)
    )

    # ... rest of code ...
```

### 5. Update Memory Generator (backend/memory/generator.py)

Add token tracking to memory generation:

```python
from backend.services.token_tracking_service import TokenTrackingService
from backend.models.token_usage import OperationType
from backend.database.session import SessionLocal

def generate_daily_memory(self, db: Session, user_id: str, date: datetime):
    # ... existing code ...

    response = self.llm.chat(messages)

    # Track token usage
    # Note: Get actual token counts from LLM response
    TokenTrackingService.track_usage(
        db=db,
        user_id=user_id,
        operation=OperationType.MEMORY_GENERATION,
        model=settings.default_llm_model,
        prompt_tokens=len(prompt.split()) * 1.3,  # Rough estimate
        completion_tokens=len(response.split()) * 1.3
    )

    # ... rest of code ...
```

### 6. Update Query Agent Runner (backend/agents/query_agent/runner.py)

Add token tracking capability:

```python
# Modify QueryState to include token counts
class QueryState(TypedDict):
    # ... existing fields ...
    prompt_tokens: int
    completion_tokens: int

# In run_query_agent, return token counts:
async def run_query_agent(...) -> Dict[str, Any]:
    # ... existing code ...

    return {
        "success": final_state.get("success", False),
        "sql": final_state.get("final_sql"),
        "result": final_state.get("final_result"),
        "error": final_state.get("error_message"),
        "prompt_tokens": final_state.get("prompt_tokens", 0),
        "completion_tokens": final_state.get("completion_tokens", 0)
    }
```

### 7. Register Routes (backend/api/routes.py)

```python
from backend.api import usage  # Add import

# In create_api_router():
api_router.include_router(usage.router)
```

## Testing & Verification

### Manual Testing Steps

1. **Make some chat requests**:
   ```bash
   # Send 3-5 chat messages
   curl -X POST http://localhost:8000/api/chat ...
   ```

2. **Check usage summary**:
   ```bash
   curl -X GET "http://localhost:8000/api/usage/summary?days=7" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Check daily breakdown**:
   ```bash
   curl -X GET "http://localhost:8000/api/usage/daily?days=7" \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

4. **Verify database records**:
   ```sql
   SELECT * FROM token_usage WHERE user_id = 'USER_ID' ORDER BY timestamp DESC LIMIT 10;
   ```

## MCP Browser Testing

Test usage dashboard (in Phase 11):
- Navigate to /usage page
- Verify charts display correctly
- Check totals match API responses

## Code Review Checklist

- [ ] Token costs calculated accurately per model
- [ ] Costs stored in USD with 4 decimal precision
- [ ] Usage tracked for all LLM operations (chat, memory, query)
- [ ] Daily aggregation works correctly across timezones
- [ ] Auth required on all usage endpoints
- [ ] User can only see their own usage
- [ ] Pricing table easy to update when rates change

## Done Criteria

1. Token usage tracked for chat operations
2. Token usage tracked for memory generation
3. Token usage tracked for query agent
4. Usage summary API returns correct totals
5. Daily usage API returns daily breakdown
6. Cost calculation accurate for configured models
7. Database stores all usage records
8. Unit tests pass

## Rollback Plan

If this phase fails:
1. Remove backend/services/token_tracking_service.py
2. Remove backend/api/usage.py
3. Remove backend/schemas/usage.py
4. Revert changes to chat.py, memory/generator.py, query_agent/runner.py
5. Remove usage routes from backend/api/routes.py
