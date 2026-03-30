"""Add profiling fields to database_connections and data_context to dashboards.

Revision ID: o9i0j1k2l3m4
Revises: n8h9i0j1k2l3
Create Date: 2026-03-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "o9i0j1k2l3m4"
down_revision = "n8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- DatabaseConnection: profiling fields ---
    op.add_column(
        "database_connections",
        sa.Column("profiling_status", sa.String(), server_default="pending", nullable=False),
    )
    op.add_column(
        "database_connections",
        sa.Column("profiling_progress", sa.String(), nullable=True),
    )
    op.add_column(
        "database_connections",
        sa.Column("profiling_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "database_connections",
        sa.Column("profiling_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "database_connections",
        sa.Column("profiling_completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "database_connections",
        sa.Column("data_context_path", sa.String(), nullable=True),
    )

    # --- Dashboard: data_context ---
    op.add_column(
        "dashboards",
        sa.Column("data_context", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dashboards", "data_context")
    op.drop_column("database_connections", "data_context_path")
    op.drop_column("database_connections", "profiling_completed_at")
    op.drop_column("database_connections", "profiling_started_at")
    op.drop_column("database_connections", "profiling_error")
    op.drop_column("database_connections", "profiling_progress")
    op.drop_column("database_connections", "profiling_status")
