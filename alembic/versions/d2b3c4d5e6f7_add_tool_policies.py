"""Add tool catalog and team policies

Revision ID: d2b3c4d5e6f7
Revises: c1a2b3d4e5f6
Create Date: 2026-02-24 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'd2b3c4d5e6f7'
down_revision = 'c1a2b3d4e5f6'
branch_labels = None
depends_on = None

_SEED_TOOLS = [
    ("list_tables", "List Tables", "List all tables in a database connection", "data"),
    ("get_table_schema", "Get Table Schema", "Get column definitions and row count for a table", "data"),
    ("search_tables", "Search Tables", "Search tables and columns by keyword", "data"),
    ("execute_query", "Execute SQL Query", "Execute a read-only SQL SELECT query", "data"),
    ("rag_search", "RAG Search", "Search uploaded documents using semantic search", "document"),
    ("recall_memory", "Recall Memory", "Recall past conversation context", "memory"),
    ("summarize_text", "Summarize Text", "Summarize a long text into key points", "skill"),
]


def upgrade():
    op.create_table(
        'tool_catalog',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tool_key', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.Enum('data', 'document', 'memory', 'skill', name='toolcategory'), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tool_key'),
    )

    op.create_table(
        'team_tool_policies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('tool_key', sa.String(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'tool_key', name='uq_team_tool_policies_team_tool'),
    )

    op.create_table(
        'team_connection_policies',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('connection_id', sa.Integer(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id']),
        sa.ForeignKeyConstraint(['connection_id'], ['database_connections.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'connection_id', name='uq_team_connection_policies_team_conn'),
    )

    # Seed tool catalog
    bind = op.get_bind()
    import uuid
    now = datetime.utcnow().isoformat()
    for tool_key, display_name, description, category in _SEED_TOOLS:
        bind.execute(sa.text(
            "INSERT INTO tool_catalog (id, tool_key, display_name, description, category, is_system, created_at) "
            "VALUES (:id, :tool_key, :display_name, :description, :category, true, :now)"
        ), {
            "id": str(uuid.uuid4()),
            "tool_key": tool_key,
            "display_name": display_name,
            "description": description,
            "category": category,
            "now": now,
        })


def downgrade():
    op.drop_table('team_connection_policies')
    op.drop_table('team_tool_policies')
    op.drop_table('tool_catalog')
    op.execute("DROP TYPE IF EXISTS toolcategory")
