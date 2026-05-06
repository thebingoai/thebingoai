"""SQLAlchemy models for dbt transforms (Phase 4)."""
import uuid as _uuid
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from backend.database.base import Base, TimestampMixin


class DbtModel(Base, TimestampMixin):
    __tablename__ = "dbt_models"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    owner_scope_kind = Column(String(8), nullable=False)   # user | team | org
    owner_scope_id = Column(String, nullable=False)
    name = Column(String(255), nullable=False)             # becomes the DataPlane table name
    sql = Column(Text, nullable=False)
    materialization = Column(String(16), nullable=False, default="table")  # table | view | incremental
    unique_key = Column(String(255), nullable=True)        # required for incremental
    cron = Column(String(64), nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(16), nullable=True)
    last_profile_columns = Column(JSONB, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("owner_scope_kind", "owner_scope_id", "name",
                         name="uq_dbt_model_scope_name"),
        Index("ix_dbt_model_enabled_next_run", "enabled", "next_run_at"),
    )


class DbtRun(Base):
    __tablename__ = "dbt_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    owner_scope_kind = Column(String(8), nullable=False)
    owner_scope_id = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="running")
    # running | success | partial_success | failed
    models_run = Column(JSONB, nullable=True)              # [{name, status, rows_affected}]
    manifest_blob = Column(BYTEA, nullable=True)           # GZip-compressed manifest.json
    triggered_by = Column(String(16), nullable=False)      # cron | manual | api
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_dbt_run_scope_started", "owner_scope_kind", "owner_scope_id", "started_at"),
    )
