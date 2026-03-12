"""add sso fields to users

Revision ID: a4b5c6d7e8f9
Revises: f9a0b1c2d3e4
Create Date: 2026-03-12 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4b5c6d7e8f9'
down_revision = 'f9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make hashed_password nullable (for OAuth-only accounts)
    op.alter_column('users', 'hashed_password', nullable=True)

    # Add sso_id column
    op.add_column('users', sa.Column('sso_id', sa.String(), nullable=True))
    op.create_index('ix_users_sso_id', 'users', ['sso_id'], unique=True)

    # Add auth_provider column
    op.add_column('users', sa.Column('auth_provider', sa.String(), nullable=False, server_default='local'))

    # Data migration: tag all pre-existing users as local auth (server_default covers new rows)
    op.execute("UPDATE users SET auth_provider = 'local'")


def downgrade() -> None:
    op.drop_column('users', 'auth_provider')
    op.drop_index('ix_users_sso_id', table_name='users')
    op.drop_column('users', 'sso_id')
    op.alter_column('users', 'hashed_password', nullable=False)
