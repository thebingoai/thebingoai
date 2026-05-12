"""Add managed_by to data_planes.

Distinguishes Bingo-managed (auto-provisioned in INTERNAL_GCP_PROJECT) from
Customer-managed (BYO paste-SA) rows. UI gates Edit/Delete on Bingo-managed;
backend rejects destructive ops as defence-in-depth.

Valid values (Python-side enum): {customer, bingo}.

Revision ID: dpm2b3c4d5e6
Revises: ops1a2b3c4d5
Create Date: 2026-05-12 18:30:01.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "dpm2b3c4d5e6"
down_revision = "ops1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_planes",
        sa.Column(
            "managed_by",
            sa.String(length=16),
            nullable=False,
            server_default="customer",
        ),
    )
    # Defensive backfill: any pre-existing row that looks Bingo-managed
    # (system-created, GCP type) gets flagged. Expected to be a no-op on
    # current data because pre-Shape-A internal fallback never created
    # rows — but cheap insurance for any manually-inserted internal rows.
    op.execute(
        """
        UPDATE data_planes
           SET managed_by = 'bingo'
         WHERE type = 'google_cloud_project'
           AND credentials_encrypted IS NOT NULL
           AND owner_scope_kind = 'org'
           AND created_by_user_id IS NULL
        """
    )


def downgrade():
    op.drop_column("data_planes", "managed_by")
