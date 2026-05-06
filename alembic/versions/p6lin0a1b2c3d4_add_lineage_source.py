"""Phase 6: merge phase-3 + phase-4 heads, add source enum to widgets_pending_manual_rewrite

Revision ID: p6lin0a1b2c3d4
Revises: b2c3d4e5f6a7, dbt0a1b2c3d4e5
Create Date: 2026-05-06 14:30:00.000000

Notes:
- Merges the phase-3 (migration_journal) and phase-4 (dbt_transforms) heads.
- Adds widgets_pending_manual_rewrite.source ('migration' | 'parse_failure') so the
  same review queue can disambiguate Phase 3 substrate rewrites from Phase 6
  lineage parse failures.
- Widget-level lineage_status is stored as a key inside the JSON entry in
  dashboards.widgets (no new column — widgets are not their own table).
"""
from alembic import op
import sqlalchemy as sa


revision = 'p6lin0a1b2c3d4'
down_revision = ('b2c3d4e5f6a7', 'dbt0a1b2c3d4e5')
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "widgets_pending_manual_rewrite",
        sa.Column("source", sa.String(16), nullable=False, server_default="migration"),
    )
    op.create_index(
        "ix_widgets_pending_manual_rewrite_source",
        "widgets_pending_manual_rewrite",
        ["source"],
    )


def downgrade():
    op.drop_index(
        "ix_widgets_pending_manual_rewrite_source",
        table_name="widgets_pending_manual_rewrite",
    )
    op.drop_column("widgets_pending_manual_rewrite", "source")
