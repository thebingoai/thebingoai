"""Phase G v1.a: add acl_grants table for resource-level access control.

Revision ID: g1av1a1b2c3d4
Revises: g0v0a1b2c3d4
Create Date: 2026-05-08

`acl_grants` records explicit resource→principal→permission tuples consumed by
the bingo-org-governance plugin. Community ships only the schema; eval logic
lives in the plugin.

`resource_id` is varchar(64) to fit the various id shapes:
- UUID strings (connection.uuid, pipeline.id, dbt_models.id)
- "scope_kind:scope_id:table_name" composite for dataplane_table grants

`principal_id` is varchar(64) for similar flexibility:
- user UUID, team UUID
- "role:data_admin" / "role:member" / "role:team_admin" for role-based grants
"""
from alembic import op
import sqlalchemy as sa


revision = "g1av1a1b2c3d4"
down_revision = "g0v0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "acl_grants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("principal_type", sa.String(16), nullable=False),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("permission", sa.String(16), nullable=False),
        sa.Column("granted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("granted_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint(
            "resource_type", "resource_id", "principal_type", "principal_id", "permission",
            name="uq_acl_grant",
        ),
    )
    op.create_index("ix_acl_grants_resource", "acl_grants", ["resource_type", "resource_id"])
    op.create_index("ix_acl_grants_principal", "acl_grants", ["principal_type", "principal_id"])


def downgrade() -> None:
    op.drop_index("ix_acl_grants_principal", table_name="acl_grants")
    op.drop_index("ix_acl_grants_resource", table_name="acl_grants")
    op.drop_table("acl_grants")
