import os
import uuid

from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base, TimestampMixin


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False)
    feature_flags = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'"),
        default=dict,
    )
    # Subscription lifecycle. Python-side enum:
    # {trial, active, past_due, expired, cancelled}. Default 'trial'.
    plan_state = Column(
        String(32),
        nullable=False,
        server_default="trial",
        default="trial",
    )
    trial_expires_at = Column(DateTime(timezone=True), nullable=True)
    credit_balance = Column(
        Integer,
        nullable=False,
        server_default="5000",
        default=lambda: int(os.environ.get("DEFAULT_ORG_CREDITS", "5000")),
    )
    is_archived = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
    )
