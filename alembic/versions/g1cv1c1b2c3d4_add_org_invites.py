"""Phase G v1.c.2: add org_invites table for organization invitations.

Revision ID: g1cv1c1b2c3d4
Revises: g1av1a1b2c3d4
Create Date: 2026-05-08

`token_hash` stores the SHA256 hash of the invite token; the raw token is
returned exactly once at create-time and embedded in the activation link.
"""
from alembic import op
import sqlalchemy as sa


revision = "g1cv1c1b2c3d4"
down_revision = "g1av1a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_invites",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_org_invites_org_email", "org_invites", ["org_id", "email"])
    op.create_index("ix_org_invites_pending", "org_invites", ["org_id", "activated_at"])


def downgrade() -> None:
    op.drop_index("ix_org_invites_pending", table_name="org_invites")
    op.drop_index("ix_org_invites_org_email", table_name="org_invites")
    op.drop_table("org_invites")
