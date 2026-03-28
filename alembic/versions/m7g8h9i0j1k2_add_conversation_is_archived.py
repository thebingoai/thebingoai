"""Add is_archived column to conversations table.

Revision ID: m7g8h9i0j1k2
Revises: l6f7g8h9i0j1
Create Date: 2026-03-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "m7g8h9i0j1k2"
down_revision = "l6f7g8h9i0j1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_conversations_user_archived",
        "conversations",
        ["user_id", "is_archived"],
    )


def downgrade():
    op.drop_index("ix_conversations_user_archived", table_name="conversations")
    op.drop_column("conversations", "is_archived")
