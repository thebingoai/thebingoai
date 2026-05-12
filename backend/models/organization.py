from sqlalchemy import Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from backend.database.base import Base, TimestampMixin
import uuid


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
