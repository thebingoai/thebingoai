import sys
from pathlib import Path
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.base import Base
from backend.config import settings

# Import all models to register them with Base
from backend.models import (
    user, database_connection, conversation, message, agent_step, token_usage,
    organization, team, team_membership, tool_catalog, team_tool_policy,
    team_connection_policy, custom_agent, heartbeat_job, heartbeat_job_run,
    skill_reference, skill_suggestion, dashboard, agent_session, agent_message,
)

config = context.config
# Use direct connection URL if available (bypasses PgBouncer for migrations)
db_url = getattr(settings, 'database_url_direct', None) or settings.database_url
config.set_main_option('sqlalchemy.url', db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
