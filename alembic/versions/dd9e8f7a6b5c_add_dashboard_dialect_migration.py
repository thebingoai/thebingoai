"""Add dashboard_dialect_migration journal.

Per-dashboard marker for the Phase 3 DuckDB cutover: a row means the dashboard's
stored SQL is DuckDB (serving may use the DuckDB path). status='migrated' rows
keep the original per-widget SQL for rollback; status='born_duckdb' rows are
dashboards created after the agent flip (already DuckDB, nothing to roll back).

Revision ID: dd9e8f7a6b5c
Revises: rl1a2b3c4d5e
Create Date: 2026-05-25 00:00:01.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "dd9e8f7a6b5c"
down_revision = "rl1a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dashboard_dialect_migration",
        sa.Column("dashboard_id", sa.Integer(), sa.ForeignKey("dashboards.id"), primary_key=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("widget_rewrites", JSONB(), nullable=False, server_default="[]"),
        sa.Column("migrated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("dashboard_dialect_migration")
