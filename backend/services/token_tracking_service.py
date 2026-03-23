"""Token usage tracking service."""

from sqlalchemy.orm import Session
from backend.models.token_usage import TokenUsage, OperationType
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# Token pricing (per 1M tokens) - updated 2026
TOKEN_PRICING = {
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-20241022": {"input": 1.0, "output": 5.0},
    "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
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
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost
        )

        db.add(usage)
        db.commit()
        db.refresh(usage)

        logger.info(f"Tracked {total_tokens} tokens for user {user_id}, operation {operation.value}, cost ${cost:.4f}")
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
        total_input_tokens = sum(r.prompt_tokens for r in records)
        total_output_tokens = sum(r.completion_tokens for r in records)
        total_cost = sum(r.cost for r in records)
        total_operations = len(records)

        # Group by operation type
        by_operation = {}
        for op_type in OperationType:
            op_records = [r for r in records if r.operation == op_type]
            by_operation[op_type.value] = {
                "count": len(op_records),
                "tokens": sum(r.total_tokens for r in op_records),
                "cost": round(sum(r.cost for r in op_records), 4)
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
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
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

        # Round costs
        for day_data in daily_usage.values():
            day_data["cost"] = round(day_data["cost"], 4)

        # Convert to sorted list
        return sorted(daily_usage.values(), key=lambda x: x["date"])
