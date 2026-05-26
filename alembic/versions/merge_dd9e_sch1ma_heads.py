"""merge dd9e8f7a6b5c and sch1ma2jsonb3 heads

Revision ID: merge_dd9e_sch1ma
Revises: ('dd9e8f7a6b5c', 'sch1ma2jsonb3')
Create Date: 2026-05-25

"""

from alembic import op
import sqlalchemy as sa

revision = 'merge_dd9e_sch1ma'
down_revision = ('dd9e8f7a6b5c', 'sch1ma2jsonb3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
