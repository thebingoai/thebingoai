"""Add feature_flags JSONB to organizations (Phase 0 — preflight).

Revision ID: f1e0a7b3c5d9
Revises: z0b1c2d3e4f5
Create Date: 2026-05-05 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f1e0a7b3c5d9"
down_revision = "z0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column(
            "feature_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade():
    op.drop_column("organizations", "feature_flags")
