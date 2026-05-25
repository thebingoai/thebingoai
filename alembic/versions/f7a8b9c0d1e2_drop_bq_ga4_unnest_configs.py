"""drop bq_ga4_unnest_configs

Revision ID: f7a8b9c0d1e2
Revises: c4e5f6a7b8d9
Create Date: 2026-05-20

NOTE: This migration is deferred — ops must verify the migrate_bigquery_to_ga4
script has been run + verified in all environments before applying. It is
committed but NOT bundled into the same release as the rename. Apply with
`alembic upgrade f7a8b9c0d1e2` once ready.
"""
from alembic import op
import sqlalchemy as sa


revision = "f7a8b9c0d1e2"
down_revision = "c4e5f6a7b8d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bq_ga4_unnest_configs")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS bq_ga4_unnest_configs (
            id                   SERIAL PRIMARY KEY,
            connection_id        INTEGER NOT NULL,
            analytics_dataset_id TEXT    NOT NULL,
            bingo_dataset_id     TEXT    NOT NULL,
            tag_name             TEXT,
            lookback_days        INTEGER NOT NULL DEFAULT 2,
            schedule_cron        TEXT    NOT NULL DEFAULT '0 6 * * *',
            enabled              BOOLEAN NOT NULL DEFAULT TRUE,
            discovered_params    JSONB,
            last_run_at          TIMESTAMP WITH TIME ZONE,
            next_run_at          TIMESTAMP WITH TIME ZONE,
            last_run_status      TEXT,
            last_run_error       TEXT,
            created_at           TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT bq_ga4_configs_conn_ds_unique UNIQUE (connection_id, analytics_dataset_id)
        )
    """)
