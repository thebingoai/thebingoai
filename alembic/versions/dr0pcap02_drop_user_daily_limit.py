"""Release 2: drop user_credit_balances.daily_limit.

Revision ID: dr0pcap02
Revises: cr3d1tcap01
Create Date: 2026-08-05

The contract half of removing the per-user daily credit cap. The expand half —
code that no longer reads the column — shipped in release 1; this drops the
column once that code is deployed everywhere.

DO NOT MERGE OR DEPLOY THIS BEFORE RELEASE 1 IS LIVE ON EVERY BACKEND REPLICA.
``scripts/deploy-k8s.sh`` runs the migrate Job to completion *before* rolling
the backend Deployment, and ``k8s/base/backend.yaml`` rolls with maxSurge: 0 /
maxUnavailable: 1, so a pod on the previous image serves for the whole rollout.
If that previous image still reads the column, this drop returns 500s from
GET /api/credits/balance — an endpoint hit on every page load and after every
chat turn — for the length of the deploy. That is the failure release 1 exists
to prevent; dropping early reintroduces it.

Conditional in both directions. A database healed by cr3d1tcap01 is
indistinguishable from one that never drifted, but anything that skipped that
repair — a restored snapshot, a manual stamp — would make an unconditional
drop fail with "column does not exist", and an unconditional re-add fail with
"column already exists".
"""

from alembic import op


revision = "dr0pcap02"
down_revision = "cr3d1tcap01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_credit_balances DROP COLUMN IF EXISTS daily_limit")


def downgrade() -> None:
    # Matches the original definition in t4n5o6p7q8r9_add_credit_system_tables.
    # server_default backfills existing rows so the NOT NULL holds.
    op.execute(
        "ALTER TABLE user_credit_balances "
        "ADD COLUMN IF NOT EXISTS daily_limit INTEGER NOT NULL DEFAULT 180"
    )
