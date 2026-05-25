"""Drop orphaned Default org in per-user-org deployments

Removes the backfill `Default` org + team created unconditionally by
c1a2b3d4e5f6. Under PER_USER_ORG_SIGNUP=true every signup gets its own Org, so
`Default` is never used and shows up empty in the admin Orgs list.

Guarded twice so community (per_user_org_signup=false, which routes users INTO
the Default org/team) is never affected:
  1. Only runs when PER_USER_ORG_SIGNUP is truthy.
  2. Only deletes when nothing references the default org/team.

Revision ID: a7b8c9d0e1f2
Revises: g8h9i0j1k2l3
Create Date: 2026-05-25 00:00:00.000000

"""
import os

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'g8h9i0j1k2l3'
branch_labels = None
depends_on = None

DEFAULT_ORG_ID = 'org-default-00000000-0000-0000-0000'
DEFAULT_TEAM_ID = 'team-default-00000000-0000-0000-0000'


def _truthy(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def upgrade():
    # Gate 1: only per-user-org deployments. Community keeps the shared Default.
    if not _truthy(os.environ.get("PER_USER_ORG_SIGNUP", "false")):
        return

    bind = op.get_bind()

    # Gate 2: never delete a Default org that is actually in use.
    in_use = bind.execute(sa.text(
        "SELECT "
        "  (SELECT count(*) FROM team_memberships WHERE team_id = :team) "
        "+ (SELECT count(*) FROM users WHERE org_id = :org) "
        "+ (SELECT count(*) FROM database_connections WHERE org_id = :org) "
        "+ (SELECT count(*) FROM agent_profiles WHERE org_id = :org)"
    ), {"team": DEFAULT_TEAM_ID, "org": DEFAULT_ORG_ID}).scalar()
    if (in_use or 0) > 0:
        return

    # FK-safe order: tool policies -> team -> org. Governance/admin rows FK org
    # with ondelete=CASCADE; dashboards.org_id is SET NULL.
    bind.execute(sa.text(
        "DELETE FROM team_tool_policies WHERE team_id = :team"
    ), {"team": DEFAULT_TEAM_ID})
    bind.execute(sa.text(
        "DELETE FROM teams WHERE id = :team"
    ), {"team": DEFAULT_TEAM_ID})
    bind.execute(sa.text(
        "DELETE FROM organizations WHERE id = :org"
    ), {"org": DEFAULT_ORG_ID})


def downgrade():
    # One-way data cleanup; recreating an empty Default org is not desirable.
    pass
