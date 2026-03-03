"""Add conversation type, message source, and permanent conversation per user

Revision ID: f8a9b0c1d2e3
Revises: e6f7a8b9c0d1
Create Date: 2026-03-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = "f8a9b0c1d2e3"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add `type` column to conversations
    op.add_column(
        "conversations",
        sa.Column("type", sa.String(20), nullable=False, server_default="task"),
    )

    # 2. Add partial unique index (one permanent conversation per user)
    op.create_index(
        "ix_conversations_user_permanent",
        "conversations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("type = 'permanent'"),
    )

    # 3. Add `source` column to messages
    op.add_column(
        "messages",
        sa.Column("source", sa.String(20), nullable=False, server_default="chat"),
    )

    # 4. Add `heartbeat_job_id` FK to messages
    op.add_column(
        "messages",
        sa.Column(
            "heartbeat_job_id",
            sa.String(),
            sa.ForeignKey("heartbeat_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 5. Data migration: create a permanent conversation for each existing user
    connection = op.get_bind()
    users = connection.execute(sa.text("SELECT id FROM users")).fetchall()
    for (user_id,) in users:
        thread_id = str(uuid.uuid4())
        connection.execute(
            sa.text(
                """
                INSERT INTO conversations (thread_id, user_id, title, type, created_at, updated_at)
                VALUES (:thread_id, :user_id, 'Bingo AI', 'permanent', NOW(), NOW())
                """
            ),
            {"thread_id": thread_id, "user_id": user_id},
        )


def downgrade():
    op.drop_index("ix_conversations_user_permanent", table_name="conversations")
    op.drop_column("messages", "heartbeat_job_id")
    op.drop_column("messages", "source")
    # Remove all permanent conversations before dropping column
    op.execute(sa.text("DELETE FROM conversations WHERE type = 'permanent'"))
    op.drop_column("conversations", "type")
