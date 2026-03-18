"""Add agent_sessions and agent_messages tables for peer-to-peer agent mesh.

Revision ID: g1a2b3c4d5e6
Revises: f9a0b1c2d3e4
Create Date: 2026-03-18 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "g1a2b3c4d5e6"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("agent_definition_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["agent_definition_id"], ["custom_agents.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"])
    op.create_index(
        "ix_agent_sessions_user_type", "agent_sessions", ["user_id", "agent_type"]
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("from_session_id", sa.String(), nullable=False),
        sa.Column("to_session_id", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False, server_default="request"),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["from_session_id"], ["agent_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["to_session_id"], ["agent_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_messages_correlation_id", "agent_messages", ["correlation_id"])
    op.create_index(
        "ix_agent_messages_to_status", "agent_messages", ["to_session_id", "status"]
    )
    op.create_index("ix_agent_messages_user_id", "agent_messages", ["user_id"])


def downgrade():
    op.drop_index("ix_agent_messages_user_id", table_name="agent_messages")
    op.drop_index("ix_agent_messages_to_status", table_name="agent_messages")
    op.drop_index("ix_agent_messages_correlation_id", table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index("ix_agent_sessions_user_type", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
