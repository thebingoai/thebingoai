"""merge migration heads

Revision ID: 1943d5e906c2
Revises: c2d3e4f5a6b7, i3c4d5e6f7g8
Create Date: 2026-03-19 10:01:46.055085

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1943d5e906c2'
down_revision = ('c2d3e4f5a6b7', 'i3c4d5e6f7g8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
