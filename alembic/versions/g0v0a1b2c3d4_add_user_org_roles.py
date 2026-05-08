"""Phase G v0: add user_org_roles table for governance role assignments.

Revision ID: g0v0a1b2c3d4
Revises: p6lin0a1b2c3d4
Create Date: 2026-05-08

Distinct from the existing `user_roles` table (system-wide, single role per user).
This table maps users to per-Organization governance roles (`data_admin`,
`team_admin`, `member`) consumed by the bingo-org-governance plugin (Phase G).
"""
from alembic import op
import sqlalchemy as sa


revision = "g0v0a1b2c3d4"
down_revision = "p6lin0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_org_roles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("team_id", sa.String(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("granted_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("user_id", "org_id", "role", "team_id", name="uq_user_org_roles_assignment"),
    )
    op.create_index("ix_user_org_roles_user_org", "user_org_roles", ["user_id", "org_id"])
    op.create_index("ix_user_org_roles_org_role", "user_org_roles", ["org_id", "role"])


def downgrade() -> None:
    op.drop_index("ix_user_org_roles_org_role", table_name="user_org_roles")
    op.drop_index("ix_user_org_roles_user_org", table_name="user_org_roles")
    op.drop_table("user_org_roles")
