"""Add cache columns to dashboards for SQLite materialization.

Revision ID: p0j1k2l3m4n5
Revises: o9i0j1k2l3m4
Create Date: 2026-03-30 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p0j1k2l3m4n5"
down_revision = "o9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dashboards",
        sa.Column("cache_key", sa.String(500), nullable=True),
    )
    op.add_column(
        "dashboards",
        sa.Column("cache_built_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "dashboards",
        sa.Column("cache_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "dashboards",
        sa.Column("cache_date_range_days", sa.Integer(), server_default="90", nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dashboards", "cache_date_range_days")
    op.drop_column("dashboards", "cache_status")
    op.drop_column("dashboards", "cache_built_at")
    op.drop_column("dashboards", "cache_key")
