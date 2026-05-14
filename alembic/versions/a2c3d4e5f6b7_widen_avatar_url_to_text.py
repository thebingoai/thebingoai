"""widen agent_profiles.avatar_url to TEXT

Revision ID: a2c3d4e5f6b7
Revises: z1b2c3d4e5f6
Create Date: 2026-05-14

The avatar upload endpoint stores the image inline as a base64 data URL, which
trivially exceeds 500 characters for any real image. Widen to TEXT.
"""
from alembic import op
import sqlalchemy as sa


revision = "a2c3d4e5f6b7"
down_revision = "z1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "agent_profiles", "avatar_url",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "agent_profiles", "avatar_url",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
