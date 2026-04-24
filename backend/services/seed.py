"""Seed sample database connections for new users."""

import logging
import os
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.models.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)

SAMPLE_DB_PATH = "/app/data/sample/airbnb_listings.sqlite"
SAMPLE_SOURCE_MARKER = "__bingo_sample__airbnb_listings"
SAMPLE_CONNECTION_NAME = "Airbnb Listings (Sample)"


def seed_sample_connections(user_id: str, db: Session) -> None:
    """Create sample SQLite connections for a new user.

    Idempotent — skips if the sample connection already exists for the user
    or if the sample database file is not present on disk.
    """
    if not os.path.isfile(SAMPLE_DB_PATH):
        return

    existing = db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == user_id,
        DatabaseConnection.source_filename == SAMPLE_SOURCE_MARKER,
    ).first()
    if existing:
        return

    # Create connection record (mirrors sqlite_upload.py pattern)
    connection = DatabaseConnection(
        user_id=user_id,
        name=SAMPLE_CONNECTION_NAME,
        db_type="sqlite",
        host="internal",
        port=0,
        database="sqlite",
        username="sqlite",
        dataset_table_name=SAMPLE_DB_PATH,
        source_filename=SAMPLE_SOURCE_MARKER,
    )
    connection.password = "sqlite"
    connection.ssl_ca_cert = None
    db.add(connection)
    db.commit()
    db.refresh(connection)

    # Schema discovery (fast for a single-table SQLite file)
    try:
        from backend.api.sqlite_upload import _discover_sqlite_schema
        from backend.services.schema_discovery import generate_schema_json, save_schema_file

        schema_data = _discover_sqlite_schema(SAMPLE_DB_PATH)
        schema_json = generate_schema_json(
            connection_id=connection.id,
            connection_name=connection.name,
            db_type="sqlite",
            schema_data=schema_data,
        )
        schema_path = save_schema_file(connection.id, schema_json)

        connection.schema_json_path = schema_path
        connection.schema_generated_at = datetime.utcnow()
        connection.table_count = len(schema_data["table_names"])
        db.commit()
    except Exception:
        logger.warning(
            "Schema discovery failed for sample connection %s", connection.id, exc_info=True,
        )

    # Queue background profiling
    if connection.schema_json_path:
        try:
            from backend.tasks.profiling_tasks import profile_connection

            connection.profiling_status = "pending"
            db.commit()
            profile_connection.delay(connection.id)
        except Exception:
            logger.warning(
                "Failed to queue profiling for sample connection %s", connection.id, exc_info=True,
            )

    # Governance: auto-assign to user's teams
    try:
        from backend.config import settings

        if settings.enable_governance:
            from backend.models.team_membership import TeamMembership
            from backend.models.team_connection_policy import TeamConnectionPolicy

            user_memberships = (
                db.query(TeamMembership)
                .filter(TeamMembership.user_id == user_id)
                .all()
            )
            for membership in user_memberships:
                db.add(
                    TeamConnectionPolicy(
                        id=str(uuid.uuid4()),
                        team_id=membership.team_id,
                        connection_id=connection.id,
                    )
                )
            if user_memberships:
                db.commit()
    except Exception:
        logger.warning(
            "Failed to assign sample connection %s to teams", connection.id, exc_info=True,
        )

    logger.info(
        "Seeded sample connection '%s' (id=%s) for user %s",
        SAMPLE_CONNECTION_NAME, connection.id, user_id,
    )
