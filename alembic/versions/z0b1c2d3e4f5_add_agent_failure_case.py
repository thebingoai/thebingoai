"""Add agent_failure_case table for Layer-4 unresolved-turn capture

Revision ID: z0b1c2d3e4f5
Revises: y9a0b1c2d3e4
Create Date: 2026-04-18 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'z0b1c2d3e4f5'
down_revision = 'y9a0b1c2d3e4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agent_failure_case",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("thread_id", sa.String(), nullable=True),
        sa.Column("user_question", sa.Text(), nullable=False),
        sa.Column("response_initial", sa.Text(), nullable=False, server_default=""),
        sa.Column("response_after_retry", sa.Text(), nullable=False, server_default=""),
        sa.Column("judge_reason_initial", sa.Text(), nullable=False, server_default=""),
        sa.Column("judge_reason_retry", sa.Text(), nullable=False, server_default=""),
        sa.Column("judge_directive", sa.Text(), nullable=False, server_default=""),
        sa.Column("orchestrator_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("judge_model", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_failure_case_user_id", "agent_failure_case", ["user_id"])
    op.create_index("ix_agent_failure_case_conversation_id", "agent_failure_case", ["conversation_id"])
    op.create_index("ix_agent_failure_case_thread_id", "agent_failure_case", ["thread_id"])
    op.create_index("ix_agent_failure_case_created_at", "agent_failure_case", ["created_at"])


def downgrade():
    op.drop_index("ix_agent_failure_case_created_at", table_name="agent_failure_case")
    op.drop_index("ix_agent_failure_case_thread_id", table_name="agent_failure_case")
    op.drop_index("ix_agent_failure_case_conversation_id", table_name="agent_failure_case")
    op.drop_index("ix_agent_failure_case_user_id", table_name="agent_failure_case")
    op.drop_table("agent_failure_case")
