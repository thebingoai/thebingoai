"""Seed default team tool policies from tool catalog

Revision ID: a1b2c3d4e5f6
Revises: f4d5e6f7a8b9
Create Date: 2026-02-25 06:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f4d5e6f7a8b9'
branch_labels = None
depends_on = None

DEFAULT_TEAM_ID = 'team-default-00000000-0000-0000-0000'


def upgrade():
    bind = op.get_bind()
    now = datetime.utcnow().isoformat()

    # Enable all tools from the catalog for the default team
    bind.execute(sa.text(
        "INSERT INTO team_tool_policies (id, team_id, tool_key, is_enabled, created_at) "
        "SELECT gen_random_uuid()::text, :team_id, tool_key, true, :now "
        "FROM tool_catalog "
        "WHERE NOT EXISTS ("
        "  SELECT 1 FROM team_tool_policies ttp "
        "  WHERE ttp.team_id = :team_id AND ttp.tool_key = tool_catalog.tool_key"
        ")"
    ), {"team_id": DEFAULT_TEAM_ID, "now": now})


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(
        "DELETE FROM team_tool_policies WHERE team_id = :team_id"
    ), {"team_id": DEFAULT_TEAM_ID})
