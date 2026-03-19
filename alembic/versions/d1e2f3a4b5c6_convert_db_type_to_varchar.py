"""convert db_type from enum to varchar

Revision ID: d1e2f3a4b5c6
Revises: 1943d5e906c2
Create Date: 2026-03-19 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = '1943d5e906c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert the ENUM column to VARCHAR(50)
    op.alter_column(
        'database_connections',
        'db_type',
        existing_type=sa.Enum('postgres', 'mysql', 'dataset', name='databasetype'),
        type_=sa.String(50),
        existing_nullable=False,
        postgresql_using='db_type::text',
    )
    # Drop the old enum type
    op.execute('DROP TYPE IF EXISTS databasetype')


def downgrade() -> None:
    # Recreate the enum type
    database_type = sa.Enum('postgres', 'mysql', 'dataset', name='databasetype')
    database_type.create(op.get_bind(), checkfirst=True)
    # Convert back to ENUM
    op.alter_column(
        'database_connections',
        'db_type',
        existing_type=sa.String(50),
        type_=database_type,
        existing_nullable=False,
        postgresql_using='db_type::databasetype',
    )
