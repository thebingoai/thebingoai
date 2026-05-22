"""Idempotently add timezone columns to schedule-bearing tables.

Revision ID: r1z2drift00
Revises: f685d85122bd
Create Date: 2026-05-19

Heals DBs that were stamped past ``b3d4e5f6a7c8`` without its DDL having run
(observed when a DB snapshot was restored or ``alembic stamp`` was used
instead of ``upgrade``). The original revision unconditionally calls
``add_column`` and would crash on a DB where the column already exists, so we
issue ADD COLUMN IF NOT EXISTS here. Safe to apply on healthy DBs — it is a
no-op when the columns are already present.
"""

from alembic import op


revision = "r1z2drift00"
down_revision = "f685d85122bd"
branch_labels = None
depends_on = None


_TABLES = ("heartbeat_jobs", "dashboards", "pipelines")


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'"
        )


def downgrade() -> None:
    pass
