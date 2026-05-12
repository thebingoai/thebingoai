"""Add plan_state + trial_expires_at to organizations.

Trial-billing primitive for Shape A (per-Org auto-provisioned internal-GCP
plane). plan_state is a String column (Python-side enum) with values
{trial, active, past_due, expired, cancelled}; default 'trial' so existing
orgs become trial rows that an admin can flip to 'active' on conversion.

Revision ID: ops1a2b3c4d5
Revises: c0d1e2f3a4b5
Create Date: 2026-05-12 18:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "ops1a2b3c4d5"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column(
            "plan_state",
            sa.String(length=32),
            nullable=False,
            server_default="trial",
        ),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "trial_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("organizations", "trial_expires_at")
    op.drop_column("organizations", "plan_state")
