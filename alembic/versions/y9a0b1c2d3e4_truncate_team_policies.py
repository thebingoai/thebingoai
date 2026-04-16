"""Truncate team policy tables (governance disabled)

Revision ID: y9a0b1c2d3e4
Revises: x8q9r0s1t2u3
Create Date: 2026-04-16 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'y9a0b1c2d3e4'
down_revision = 'x8q9r0s1t2u3'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM team_tool_policies"))
    bind.execute(sa.text("DELETE FROM team_connection_policies"))


def downgrade():
    # No-op: policies were runtime data, not recoverable
    pass
