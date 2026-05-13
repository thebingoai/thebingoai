"""org credit pool + role rename to bingo_admin

Revision ID: h0i1j2k3l4m5
Revises: gfb1c2d3e4f5
Create Date: 2026-05-13

Phase 0 of multi-user-org feature:
- organizations.credit_balance (org-level credit pool, default 5000)
- organizations.is_archived (soft-delete for orgs vacated by invite acceptance)
- dashboards.org_id (backfilled from users.org_id, then NOT NULL)
- org_credit_topups (audit table for BingoAdmin credit grants)
- data migration: user_roles.role 'admin' -> 'bingo_admin'
"""
from alembic import op
import sqlalchemy as sa


revision = "h0i1j2k3l4m5"
down_revision = "gfb1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "credit_balance",
            sa.Integer(),
            nullable=False,
            server_default="5000",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.add_column(
        "dashboards",
        sa.Column("org_id", sa.String(), nullable=True),
    )
    op.execute(
        """
        UPDATE dashboards d
        SET org_id = u.org_id
        FROM users u
        WHERE d.user_id = u.id AND u.org_id IS NOT NULL;
        """
    )
    op.create_foreign_key(
        "fk_dashboards_org_id",
        source_table="dashboards",
        referent_table="organizations",
        local_cols=["org_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_dashboards_org_id", "dashboards", ["org_id"])

    op.create_table(
        "org_credit_topups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "org_id",
            sa.String(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "bingo_admin_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_org_credit_topups_org_created",
        "org_credit_topups",
        ["org_id", sa.text("created_at DESC")],
    )

    op.execute(
        "UPDATE user_roles SET role = 'bingo_admin' WHERE role = 'admin';"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE user_roles SET role = 'admin' WHERE role = 'bingo_admin';"
    )

    op.drop_index("ix_org_credit_topups_org_created", table_name="org_credit_topups")
    op.drop_table("org_credit_topups")

    op.drop_index("ix_dashboards_org_id", table_name="dashboards")
    op.drop_constraint("fk_dashboards_org_id", "dashboards", type_="foreignkey")
    op.drop_column("dashboards", "org_id")

    op.drop_column("organizations", "is_archived")
    op.drop_column("organizations", "credit_balance")
