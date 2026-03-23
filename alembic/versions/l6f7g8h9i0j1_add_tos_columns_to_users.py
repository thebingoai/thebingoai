"""Add T&C acceptance columns to users table.

Revision ID: l6f7g8h9i0j1
Revises: j4d5e6f7g8h9
Create Date: 2026-03-23 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "l6f7g8h9i0j1"
down_revision = "j4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("accepted_tos", sa.Boolean(), nullable=True, server_default="false"))
    op.add_column("users", sa.Column("tos_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("tos_version", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("users", "tos_version")
    op.drop_column("users", "tos_accepted_at")
    op.drop_column("users", "accepted_tos")
