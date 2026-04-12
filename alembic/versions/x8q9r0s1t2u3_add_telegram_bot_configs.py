"""add telegram_bot_configs table

Revision ID: x8q9r0s1t2u3
Revises: w7p8q9r0s1t2
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'x8q9r0s1t2u3'
down_revision = 'w7p8q9r0s1t2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telegram_bot_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('bot_token_encrypted', sa.String(), nullable=False),
        sa.Column('bot_username', sa.String(), nullable=True),
        sa.Column('webhook_secret', sa.String(length=64), nullable=False),
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )


def downgrade() -> None:
    op.drop_table('telegram_bot_configs')
