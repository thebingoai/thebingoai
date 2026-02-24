"""Add org/team models

Revision ID: c1a2b3d4e5f6
Revises: a3f8e2b1c9d4
Create Date: 2026-02-24 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1a2b3d4e5f6'
down_revision = 'a3f8e2b1c9d4'
branch_labels = None
depends_on = None


def upgrade():
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # Create teams table
    op.create_table(
        'teams',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('org_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'name', name='uq_teams_org_name'),
    )

    # Create team_memberships table
    op.create_table(
        'team_memberships',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('admin', 'member', name='memberrole'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'team_id', name='uq_team_memberships_user_team'),
    )

    # Add org_id to users (nullable for migration)
    op.add_column('users', sa.Column('org_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_users_org_id', 'users', 'organizations', ['org_id'], ['id'])

    # Add org_id to database_connections (nullable for migration)
    op.add_column('database_connections', sa.Column('org_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_connections_org_id', 'database_connections', 'organizations', ['org_id'], ['id'])

    # Data migration: create Default org and Default team, assign all existing users
    bind = op.get_bind()
    default_org_id = 'org-default-00000000-0000-0000-0000'
    default_team_id = 'team-default-00000000-0000-0000-0000'
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    bind.execute(sa.text(
        "INSERT INTO organizations (id, name, created_at, updated_at) "
        "VALUES (:id, :name, :now, :now)"
    ), {"id": default_org_id, "name": "Default", "now": now})

    bind.execute(sa.text(
        "INSERT INTO teams (id, org_id, name, created_at, updated_at) "
        "VALUES (:id, :org_id, :name, :now, :now)"
    ), {"id": default_team_id, "org_id": default_org_id, "name": "Default", "now": now})

    bind.execute(sa.text(
        "UPDATE users SET org_id = :org_id WHERE org_id IS NULL"
    ), {"org_id": default_org_id})

    bind.execute(sa.text(
        "UPDATE database_connections SET org_id = :org_id WHERE org_id IS NULL"
    ), {"org_id": default_org_id})


def downgrade():
    op.drop_constraint('fk_connections_org_id', 'database_connections', type_='foreignkey')
    op.drop_column('database_connections', 'org_id')

    op.drop_constraint('fk_users_org_id', 'users', type_='foreignkey')
    op.drop_column('users', 'org_id')

    op.drop_table('team_memberships')
    op.drop_table('teams')
    op.drop_table('organizations')

    op.execute("DROP TYPE IF EXISTS memberrole")
