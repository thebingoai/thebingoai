"""Rename data_plane type slug 'bigquery_gcs' to 'google_cloud_project'.

Revision ID: g3a3a1b2c3d4e
Revises: g2bv2b1c2d3e4
Create Date: 2026-05-09
"""
from alembic import op


revision = "g3a3a1b2c3d4e"
down_revision = "g2bv2b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE data_planes SET type = 'google_cloud_project' WHERE type = 'bigquery_gcs'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE data_planes SET type = 'bigquery_gcs' WHERE type = 'google_cloud_project'"
    )
