"""Add residency_locked to data_planes.

Marks a plane whose data must not leave its region. When true, DuckDB-over-GCS
serving (Phase 2) is skipped and the plane stays {BQ stored + BQ serving}.
Default false: planes serve via DuckDB once the per-Org duckdb_widget_serving
flag is on.

Revision ID: rl1a2b3c4d5e
Revises: g8h9i0j1k2l3
Create Date: 2026-05-25 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "rl1a2b3c4d5e"
down_revision = "g8h9i0j1k2l3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_planes",
        sa.Column(
            "residency_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("data_planes", "residency_locked")
