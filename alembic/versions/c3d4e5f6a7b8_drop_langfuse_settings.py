"""drop langfuse_settings table

Langfuse plugin config moved from DB-backed admin UI to environment variables
(LANGFUSE_TRACING_ENABLED + LANGFUSE_AGENT_<NAME>). The table and singleton
row added in z1b2c3d4e5f6 are no longer read or written.

Revision ID: c3d4e5f6a7b8
Revises: a2c3d4e5f6b7
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "a2c3d4e5f6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("langfuse_settings")


def downgrade() -> None:
    op.create_table(
        "langfuse_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("agent_toggles", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
    )
    op.execute(
        "INSERT INTO langfuse_settings (id, enabled, agent_toggles, updated_at) "
        "VALUES (1, false, '{}', now())"
    )
