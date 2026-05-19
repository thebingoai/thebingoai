"""Move connection context from local filesystem to database_connections.data_context (JSONB).

Backfills existing per-connection context files from `data/contexts/{id}_context.json`
into a new `data_context` JSONB column on `database_connections`, drops the now-unused
`data_context_path` String column, and removes the legacy contexts directory.

Revision ID: e6g7h8i9j0k1
Revises: d5f6a7b8c9e0
Create Date: 2026-05-18
"""
import json
import logging
import os
import shutil

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e6g7h8i9j0k1"
down_revision = "d5f6a7b8c9e0"
branch_labels = None
depends_on = None


CONTEXTS_DIR = os.environ.get("BINGO_CONTEXTS_DIR", "/app/data/contexts")
logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.add_column(
        "database_connections",
        sa.Column("data_context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    if os.path.isdir(CONTEXTS_DIR):
        bind = op.get_bind()
        backfilled = 0
        orphans = 0
        for fname in os.listdir(CONTEXTS_DIR):
            if not fname.endswith("_context.json"):
                continue
            cid_str = fname[: -len("_context.json")]
            if not cid_str.isdigit():
                continue
            cid = int(cid_str)
            fpath = os.path.join(CONTEXTS_DIR, fname)
            try:
                with open(fpath) as fh:
                    payload = json.load(fh)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("skip unreadable context file %s: %s", fpath, exc)
                continue
            res = bind.execute(
                sa.text(
                    "UPDATE database_connections "
                    "SET data_context = CAST(:payload AS JSONB) "
                    "WHERE id = :id"
                ),
                {"payload": json.dumps(payload), "id": cid},
            )
            if res.rowcount == 0:
                orphans += 1
                logger.warning(
                    "orphan context file %s (no database_connections row for id=%d)",
                    fname,
                    cid,
                )
            else:
                backfilled += 1
        logger.info(
            "backfilled %d connection contexts from %s (%d orphans)",
            backfilled,
            CONTEXTS_DIR,
            orphans,
        )

    op.drop_column("database_connections", "data_context_path")

    if os.path.isdir(CONTEXTS_DIR):
        shutil.rmtree(CONTEXTS_DIR, ignore_errors=True)


def downgrade() -> None:
    op.add_column(
        "database_connections",
        sa.Column("data_context_path", sa.String(), nullable=True),
    )
    op.drop_column("database_connections", "data_context")
