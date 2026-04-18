"""Token usage tracking service."""

from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models.token_usage import TokenUsage, OperationType
from datetime import datetime, timedelta, date
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)
credit_logger = logging.getLogger("credit")

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


class InsufficientCreditsError(Exception):
    """Raised when a user has exhausted their daily credit limit."""
    pass


class CreditContextManager:
    """
    Community-edition credit context manager.

    Checks the user's daily credit limit on entry and records one credit of
    usage on successful exit.  Mirrors the interface expected by chat.py,
    websocket.py, and the Celery task files so that the enterprise bingo_admin
    plugin can drop in as a replacement without any call-site changes.

    Supports both async (FastAPI handlers) and sync (Celery tasks) protocols.
    """

    DEFAULT_DAILY_LIMIT = 180

    def __init__(
        self,
        db: Session,
        user_id: str,
        title: str,
        provider_name,
        conversation_id,
        block_on_insufficient: bool = True,
    ):
        self.db = db
        self.user_id = user_id
        self.title = title[:83] if title else ""
        self.provider_name = provider_name
        self.conversation_id = conversation_id
        self.block_on_insufficient = block_on_insufficient
        self._voided = False
        self._void_reason: str = ""

    def void(self, reason: str = "unresolved") -> None:
        """Skip credit recording on exit.

        Called by the chat handler when Layer-4 retry still fails the judge —
        the user isn't charged for a turn that didn't resolve their question.
        Also usable by future policies (moderation, abuse filters, etc.).
        """
        self._voided = True
        self._void_reason = reason
        credit_logger.info("[credit] user %s: voided — %s", self.user_id, reason)

    # ------------------------------------------------------------------
    # Internal helpers (sync, safe to call from both async and sync paths)
    # ------------------------------------------------------------------

    def _ensure_balance_row(self) -> int:
        """Return daily_limit for this user, creating a balance row if absent."""
        row = self.db.execute(
            text("SELECT daily_limit FROM user_credit_balances WHERE user_id = :uid"),
            {"uid": self.user_id},
        ).fetchone()
        if row is None:
            self.db.execute(
                text(
                    "INSERT INTO user_credit_balances (user_id, daily_limit, created_at) "
                    "VALUES (:uid, :limit, :now)"
                ),
                {"uid": self.user_id, "limit": self.DEFAULT_DAILY_LIMIT, "now": datetime.utcnow()},
            )
            self.db.commit()
            credit_logger.info("[credit] user %s: no balance row found — created with daily_limit=%d", self.user_id, self.DEFAULT_DAILY_LIMIT)
            return self.DEFAULT_DAILY_LIMIT
        return int(row[0])

    def _today_usage(self) -> int:
        """Sum of credits_used for this user today."""
        row = self.db.execute(
            text(
                "SELECT COALESCE(SUM(credits_used), 0) FROM credit_usage "
                "WHERE user_id = :uid AND date = :today"
            ),
            {"uid": self.user_id, "today": date.today()},
        ).fetchone()
        return int(row[0]) if row else 0

    def _check(self):
        daily_limit = self._ensure_balance_row()
        used = self._today_usage()
        credit_logger.info(
            "[credit] user %s: daily_limit=%d, used_today=%d, block_on_insufficient=%s",
            self.user_id, daily_limit, used, self.block_on_insufficient,
        )
        if daily_limit == 0 or used >= daily_limit:
            credit_logger.warning(
                "[credit] user %s: daily limit %d reached (used=%d), block=%s",
                self.user_id, daily_limit, used, self.block_on_insufficient,
            )
            if self.block_on_insufficient:
                raise InsufficientCreditsError(
                    f"Daily credit limit of {daily_limit} reached."
                )

    def _record(self):
        today = date.today()
        self.db.execute(
            text(
                "INSERT INTO credit_usage "
                "(user_id, conversation_id, title, credits_used, input_tokens, output_tokens, date, created_at) "
                "VALUES (:uid, :cid, :title, 1, 0, 0, :today, :now)"
            ),
            {
                "uid": self.user_id,
                "cid": self.conversation_id,
                "title": self.title,
                "today": today,
                "now": datetime.utcnow(),
            },
        )
        self.db.commit()
        credit_logger.info(
            "[credit] user %s: recorded 1 credit — title=%r, date=%s",
            self.user_id, self.title, today,
        )

    # ------------------------------------------------------------------
    # Async context manager (FastAPI / chat / websocket)
    # ------------------------------------------------------------------

    async def __aenter__(self):
        self._check()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and not self._voided:
            self._record()
        return False

    # ------------------------------------------------------------------
    # Sync context manager (Celery tasks)
    # ------------------------------------------------------------------

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and not self._voided:
            self._record()
        return False
