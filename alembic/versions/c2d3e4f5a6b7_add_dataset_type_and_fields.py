"""add_dataset_type_and_fields

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-03-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'dataset' to the databasetype enum (IF NOT EXISTS requires pg >= 9.3)
    op.execute("ALTER TYPE databasetype ADD VALUE IF NOT EXISTS 'DATASET'")

    # Add dataset-specific columns
    op.add_column('database_connections', sa.Column('source_filename', sa.String(), nullable=True))
    op.add_column('database_connections', sa.Column('dataset_table_name', sa.String(), nullable=True))

    # Create the schema that will hold uploaded dataset tables
    op.execute("CREATE SCHEMA IF NOT EXISTS datasets")


def downgrade():
    op.execute("DROP SCHEMA IF EXISTS datasets CASCADE")
    op.drop_column('database_connections', 'dataset_table_name')
    op.drop_column('database_connections', 'source_filename')
    # Note: removing enum values requires recreating the type in PostgreSQL.
    # Leave 'dataset' in the enum and rely on application-level guards.
