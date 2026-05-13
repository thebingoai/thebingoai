"""Seed governance_v1 + governance_v2 flags onto existing organizations.

Phase G v2 GA: every Org should have governance flags set by default. New rows
are seeded in the create paths (api/organizations.py + auth/dependencies.py SSO
signup). This migration backfills any pre-existing row whose feature_flags JSONB
doesn't already carry the keys.

Forward-only state, not schema — downgrade is a no-op.

Revision ID: gfb1c2d3e4f5
Revises: dpm2b3c4d5e6
Create Date: 2026-05-13 00:00:00.000000
"""
from alembic import op


revision = "gfb1c2d3e4f5"
down_revision = "dpm2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE organizations
        SET feature_flags = COALESCE(feature_flags, '{}'::jsonb)
                         || '{"governance_v1": true, "governance_v2": true}'::jsonb
        WHERE NOT (COALESCE(feature_flags, '{}'::jsonb) ? 'governance_v2')
           OR NOT (COALESCE(feature_flags, '{}'::jsonb) ? 'governance_v1');
        """
    )


def downgrade():
    # Forward-only: flag state, not schema.
    pass
