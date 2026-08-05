"""Deferred: drop of user_credit_balances.daily_limit (now a no-op).

This revision originally dropped the column. It does nothing now, and is kept
only so the revision chain — and any `alembic_version` row that already stamped
it — stays valid.

Why it was deferred: `scripts/deploy-k8s.sh` runs the migrate Job to completion
BEFORE rolling the backend Deployment, and `k8s/base/backend.yaml` rolls with
`maxSurge: 0` / `maxUnavailable: 1`, so a pod on the previous image is always
serving during the roll. Those pods still run
`SELECT daily_limit FROM user_credit_balances` in GET /api/credits/balance — an
endpoint hit on every page load and again after every chat turn — so dropping
the column ahead of the rollout returns 500s for the length of the deploy.

Dropping a column is a *contract* step: it has to land after every reader is
gone, not before. The removal is therefore split across two releases:

    release 1 (this one)   code stops reading the column; the column stays,
                           unused. Old and new code both work against it.
    release 2 (a new       performs the drop, once release 1 is deployed
    revision, later)       everywhere and nothing reads the column.

Do not restore the drop here — add it as a new revision instead, so databases
that already ran this one still upgrade cleanly.

Revision ID: cr3d1tcap00
Revises: w1dgc4p0001
Create Date: 2026-08-04 00:00:00.000000
"""

revision = "cr3d1tcap00"
down_revision = "w1dgc4p0001"
branch_labels = None
depends_on = None


def upgrade():
    # Intentionally empty — see the module docstring. The drop moved to a
    # follow-up revision so it lands after the readers are deployed away.
    pass


def downgrade():
    # Also empty: upgrade() no longer drops the column, so re-adding it here
    # would fail with "column already exists" on any database that ran this
    # revision in its neutralised form.
    pass
