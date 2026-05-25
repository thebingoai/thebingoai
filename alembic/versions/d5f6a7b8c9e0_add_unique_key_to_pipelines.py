"""Add unique_key column to pipelines.

Stores the natural-key columns used by the DataPlane to build a snapshot
dedup view over all `dt=*` partitions. List[str] of column names — e.g.
`["ad_id", "date_start"]` for facebook_ads insights_daily. NULL means the
pipeline still pins the BQ external table to a single latest partition
(no dedup view).

Revision ID: d5f6a7b8c9e0
Revises: f7a8b9c0d1e2
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "d5f6a7b8c9e0"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipelines", sa.Column("unique_key", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("pipelines", "unique_key")
