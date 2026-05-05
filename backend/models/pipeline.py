"""SQLAlchemy models for Pipelines (Phase 2)."""
import uuid as _uuid
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.database.base import Base, TimestampMixin


class Pipeline(Base, TimestampMixin):
    __tablename__ = "pipelines"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    owner_scope_kind = Column(String(8), nullable=False)   # user | team | org
    owner_scope_id = Column(String, nullable=False)
    source_connection_id = Column(Integer, ForeignKey("database_connections.id"), nullable=False)
    data_plane_id = Column(String(36), ForeignKey("data_planes.id"), nullable=True)
    target_table = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    cron = Column(String(64), nullable=True)               # null = run-on-demand
    mode = Column(String(16), nullable=False, default="full")   # full | incremental
    incremental_key = Column(String(255), nullable=True)
    extraction_config = Column(JSONB, nullable=False, server_default="{}")
    pipeline_fingerprint = Column(String(128), nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(16), nullable=True)    # success | failed | running
    next_run_at = Column(DateTime, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(String, ForeignKey("users.id"), nullable=False)

    runs = relationship("PipelineRun", back_populates="pipeline", cascade="all, delete-orphan")
    dlt_states = relationship("DltPipelineState", back_populates="pipeline", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_scope_kind", "owner_scope_id", "pipeline_fingerprint",
                         name="uq_pipeline_scope_fingerprint"),
        Index("ix_pipeline_enabled_next_run_at", "enabled", "next_run_at"),
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    pipeline_id = Column(String(36), ForeignKey("pipelines.id"), nullable=False)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="running")  # running | success | failed
    rows_written = Column(Integer, nullable=True)
    bytes_written = Column(BigInteger, nullable=True)
    error_message = Column(Text, nullable=True)
    triggered_by = Column(String(16), nullable=False)        # cron | manual | api
    triggered_by_user_id = Column(String, nullable=True)

    pipeline = relationship("Pipeline", back_populates="runs")

    __table_args__ = (
        Index("ix_pipeline_run_pipeline_started", "pipeline_id", "started_at"),
    )


class DltPipelineState(Base):
    __tablename__ = "dlt_pipeline_states"

    id = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    owner_scope_kind = Column(String(8), nullable=False)
    owner_scope_id = Column(String, nullable=False)
    pipeline_id = Column(String(36), ForeignKey("pipelines.id"), nullable=False)
    state_blob = Column(JSONB, nullable=False, server_default="{}")
    version = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False)

    pipeline = relationship("Pipeline", back_populates="dlt_states")

    __table_args__ = (
        UniqueConstraint("pipeline_id", name="uq_dlt_state_pipeline"),
    )
