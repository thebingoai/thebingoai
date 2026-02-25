"""Backfill team memberships for existing users

Revision ID: f4d5e6f7a8b9
Revises: e3c4d5e6f7a8
Create Date: 2026-02-25 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'f4d5e6f7a8b9'
down_revision = 'e3c4d5e6f7a8'
branch_labels = None
depends_on = None

DEFAULT_TEAM_ID = 'team-default-00000000-0000-0000-0000'


def upgrade():
    bind = op.get_bind()
    now = datetime.utcnow().isoformat()

    # Insert team_memberships for all users not already in a team
    bind.execute(sa.text(
        "INSERT INTO team_memberships (id, user_id, team_id, role, created_at) "
        "SELECT gen_random_uuid()::text, u.id, :team_id, 'member', :now "
        "FROM users u "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM team_memberships tm WHERE tm.user_id = u.id AND tm.team_id = :team_id"
        ")"
    ), {"team_id": DEFAULT_TEAM_ID, "now": now})


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(
        "DELETE FROM team_memberships WHERE team_id = :team_id"
    ), {"team_id": DEFAULT_TEAM_ID})
