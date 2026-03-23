"""Add agent_profiles table and profile_id FK on custom_agents.

Revision ID: j4d5e6f7g8h9
Revises: i3c4d5e6f7g8
Create Date: 2026-03-22 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "j4d5e6f7g8h9"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_profiles table
    op.create_table(
        "agent_profiles",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("org_id", sa.String(), nullable=True),
        sa.Column("team_id", sa.String(), nullable=True),
        sa.Column("agent_type", sa.String(50), nullable=False),
        # 8 cognitive architecture sections
        sa.Column("identity", sa.Text(), nullable=False),
        sa.Column("soul", sa.Text(), nullable=True),
        sa.Column("tools", sa.Text(), nullable=True),
        sa.Column("agents", sa.Text(), nullable=True),
        sa.Column("bootstrap", sa.Text(), nullable=True),
        sa.Column("heartbeat", sa.Text(), nullable=True),
        sa.Column("user_context", sa.Text(), nullable=True),
        sa.Column("guardrails", sa.Text(), nullable=True),
        # Governance
        sa.Column("section_locks", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # Keys
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
    )

    # Indexes for common queries
    op.create_index(
        "ix_agent_profiles_user_agent_type",
        "agent_profiles",
        ["user_id", "agent_type"],
    )
    op.create_index(
        "ix_agent_profiles_team_agent_type",
        "agent_profiles",
        ["team_id", "agent_type"],
    )
    op.create_index(
        "ix_agent_profiles_org_agent_type",
        "agent_profiles",
        ["org_id", "agent_type"],
    )

    # Add profile_id FK to custom_agents
    op.add_column(
        "custom_agents",
        sa.Column("profile_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_custom_agents_profile_id",
        "custom_agents",
        "agent_profiles",
        ["profile_id"],
        ["id"],
    )


def downgrade():
    # Remove profile_id from custom_agents
    op.drop_constraint("fk_custom_agents_profile_id", "custom_agents", type_="foreignkey")
    op.drop_column("custom_agents", "profile_id")

    # Drop indexes
    op.drop_index("ix_agent_profiles_org_agent_type", "agent_profiles")
    op.drop_index("ix_agent_profiles_team_agent_type", "agent_profiles")
    op.drop_index("ix_agent_profiles_user_agent_type", "agent_profiles")

    # Drop table
    op.drop_table("agent_profiles")
