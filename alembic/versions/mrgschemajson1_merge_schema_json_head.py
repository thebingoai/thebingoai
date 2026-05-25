"""merge schema_json head into main line

Revision ID: mrgschemajson1
Revises: dd9e8f7a6b5c, sch1ma2jsonb3
Create Date: 2026-05-25

Joins the two diverged Alembic heads so `alembic upgrade head` resolves to a
single head again. The `sch1ma2jsonb3` migration (adds
database_connections.schema_json) branched off g8h9i0j1k2l3 but was never
merged back into the dd9e8f7a6b5c main line, leaving two heads — which makes
`alembic upgrade head` fail and blocks backend startup. No DDL — this is a
history-linearisation commit only.
"""
from alembic import op


revision = "mrgschemajson1"
down_revision = ("dd9e8f7a6b5c", "sch1ma2jsonb3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
