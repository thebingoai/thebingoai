"""add is_subscriber column to user_roles

Revision ID: aa2c3d4e5f6a
Revises: z1b2c3d4e5f6
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa


revision = "aa2c3d4e5f6a"
down_revision = "z1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_roles",
        sa.Column(
            "is_subscriber",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_roles", "is_subscriber")
