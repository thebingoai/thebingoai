"""Add soul_prompt and soul_version to users table

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-02-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("soul_prompt", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("soul_version", sa.Integer(), nullable=True))
    # Backfill existing rows with default soul_version = 0
    op.execute("UPDATE users SET soul_version = 0 WHERE soul_version IS NULL")
    op.alter_column("users", "soul_version", nullable=False, server_default="0")


def downgrade():
    op.drop_column("users", "soul_version")
    op.drop_column("users", "soul_prompt")
