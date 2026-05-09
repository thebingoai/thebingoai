"""merge dev sync into data-platform-v1

Revision ID: 6aa6739712fc
Revises: 1b4144c01875, g3a3a1b2c3d4e
Create Date: 2026-05-09 06:05:01.715100

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6aa6739712fc'
down_revision = ('1b4144c01875', 'g3a3a1b2c3d4e')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
