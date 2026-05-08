"""Phase G v2.b: add org_policies table for the admin policy engine.

Revision ID: g2bv2b1c2d3e4
Revises: g2av2a1b2c3d4
Create Date: 2026-05-08

Policies are an additional gate consulted after grants in the PG.6 eval
order: defaults → grants → policy (deny-overlay). A `deny` policy that
matches overrides a permit from grants; an `allow` policy can grant when
grants don't.

`kind` is "<resource_type>.<action>" style (e.g. "connection.create",
"connection.query", "pipeline.create"). The plugin's evaluator splits and
matches resource_type from the action verb.

`subject` is a JSON predicate against the resource (e.g.
{"db_type": ["postgres", "mysql"]}). Empty / NULL subject means "always
matches" (apply to all resources of this kind).

`principal_type`/`principal_id` accept "user", "team", or "role" — same
shape as acl_grants.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "g2bv2b1c2d3e4"
down_revision = "g2av2a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_policies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("org_id", sa.String(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("subject", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("effect", sa.String(8), nullable=False),
        sa.Column("principal_type", sa.String(16), nullable=False),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", sa.String(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_org_policies_org_kind", "org_policies", ["org_id", "kind"])
    op.create_index("ix_org_policies_principal", "org_policies", ["principal_type", "principal_id"])


def downgrade() -> None:
    op.drop_index("ix_org_policies_principal", table_name="org_policies")
    op.drop_index("ix_org_policies_org_kind", table_name="org_policies")
    op.drop_table("org_policies")
