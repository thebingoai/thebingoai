"""add langfuse_settings table

Revision ID: z1b2c3d4e5f6
Revises: h0i1j2k3l4m5
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa


revision = "z1b2c3d4e5f6"
down_revision = "h0i1j2k3l4m5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "langfuse_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("agent_toggles", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
    )
    # Seed the singleton row so the service always has a row to read.
    op.execute(
        "INSERT INTO langfuse_settings (id, enabled, agent_toggles, updated_at) "
        "VALUES (1, false, '{}', now())"
    )


def downgrade() -> None:
    op.drop_table("langfuse_settings")
