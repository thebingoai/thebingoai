"""Add chart_specs JSON column to messages

Revision ID: chrtspecs01
Revises: dr0pcap02
Create Date: 2026-07-17

Backs the "charts in chat" feature: holds either a frozen ad-hoc chart
snapshot (kind="adhoc") or a reference to a live dashboard widget
(kind="dashboard_widget"). See bingo/docs/superpowers/specs/2026-07-10-chat-charts-design.md.
"""
from alembic import op
import sqlalchemy as sa

revision = "chrtspecs01"
down_revision = "dr0pcap02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("messages", sa.Column("chart_specs", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("messages", "chart_specs")
