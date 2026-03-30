"""Celery tasks for connection profiling and data context generation."""

import logging
from datetime import datetime, timezone

from celery import shared_task
from backend.database.session import SessionLocal

logger = logging.getLogger(__name__)


@shared_task(name="profile_connection", bind=True, max_retries=2, time_limit=600)
def profile_connection(self, connection_id: int):
    """Profile all tables for a connection and build a data context.

    This task:
    1. Loads the already-discovered schema for the connection.
    2. Profiles each table (stats per column).
    3. Infers column roles (dimension/measure/key/attribute) and relationships.
    4. Saves the resulting data context to disk.
    5. Updates the connection's profiling_status to ``ready``.

    On failure, sets status to ``failed`` and retries up to ``max_retries``
    times with exponential back-off.
    """
    from backend.models.database_connection import DatabaseConnection
    from backend.connectors.factory import get_connector_for_connection, get_connector_registration
    from backend.services.schema_discovery import load_schema_file
    from backend.services.table_profiler import profile_table
    from backend.services.connection_context import build_connection_context, save_context_file

    db = SessionLocal()
    try:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
        ).first()
        if not connection:
            logger.warning("profile_connection: connection %d not found", connection_id)
            return

        # Mark in-progress
        connection.profiling_status = "in_progress"
        connection.profiling_error = None
        connection.profiling_started_at = datetime.now(timezone.utc)
        db.commit()

        # Load the schema that was already discovered at connection creation
        try:
            schema_json = load_schema_file(connection_id)
        except FileNotFoundError:
            connection.profiling_status = "failed"
            connection.profiling_error = "Schema file not found. Please refresh the connection schema first."
            db.commit()
            return

        # Determine connector metadata
        reg = get_connector_registration(connection.db_type)
        is_dataset = reg is not None and reg.sql_dialect_hint is not None and "SQLite" in reg.sql_dialect_hint
        db_type_str = "mysql" if connection.db_type == "mysql" else "postgres"

        # Collect all tables from all schemas
        tables_to_profile: list[tuple[str, str, dict]] = []  # (schema_name, table_name, table_data)
        for schema_name, schema_data in schema_json.get("schemas", {}).items():
            for table_name, table_data in schema_data.get("tables", {}).items():
                tables_to_profile.append((schema_name, table_name, table_data))

        total = len(tables_to_profile)
        logger.info("profile_connection %d: profiling %d table(s)", connection_id, total)

        # Profile each table
        table_profiles: dict[str, dict] = {}

        connector = get_connector_for_connection(connection)
        try:
            for idx, (schema_name, table_name, table_data) in enumerate(tables_to_profile, 1):
                # Update progress
                connection.profiling_progress = f"{idx}/{total} tables"
                db.commit()

                try:
                    result = profile_table(
                        connector=connector,
                        table_name=table_name,
                        schema_name=schema_name,
                        columns=table_data.get("columns", []),
                        row_count=table_data.get("row_count", 0),
                        db_type=db_type_str,
                        is_dataset=is_dataset,
                    )
                    table_profiles[table_name] = result
                except Exception as table_err:
                    logger.warning(
                        "profile_connection %d: failed to profile table %s: %s",
                        connection_id, table_name, table_err,
                    )
                    table_profiles[table_name] = {"table_name": table_name, "columns": {}, "error": str(table_err)}
        finally:
            connector.close()

        # Build context from schema + profiles
        context = build_connection_context(connection_id, schema_json, table_profiles)

        # Save to disk
        context_path = save_context_file(connection_id, context)

        # Mark ready
        connection.profiling_status = "ready"
        connection.profiling_progress = f"{total}/{total} tables"
        connection.profiling_completed_at = datetime.now(timezone.utc)
        connection.data_context_path = context_path
        db.commit()

        logger.info("profile_connection %d: completed — %d tables profiled", connection_id, total)

    except Exception as e:
        logger.error("profile_connection %d failed: %s", connection_id, e)
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
            ).first()
            if connection:
                connection.profiling_status = "failed"
                connection.profiling_error = str(e)
                db.commit()
        except Exception:
            db.rollback()

        # Retry with exponential back-off (60s, 120s)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


@shared_task(name="backfill_profile_all_connections")
def backfill_profile_all_connections():
    """One-time task: queue profiling for all existing connections that have
    a schema but no data context yet.

    Called on app startup to migrate existing connections after the feature is
    deployed.
    """
    from backend.models.database_connection import DatabaseConnection

    db = SessionLocal()
    try:
        pending = (
            db.query(DatabaseConnection)
            .filter(
                DatabaseConnection.profiling_status == "pending",
                DatabaseConnection.schema_json_path.isnot(None),
            )
            .all()
        )

        if not pending:
            logger.info("backfill_profile_all_connections: no pending connections")
            return

        logger.info("backfill_profile_all_connections: queuing %d connection(s)", len(pending))
        for conn in pending:
            profile_connection.delay(conn.id)

    except Exception as e:
        logger.error("backfill_profile_all_connections failed: %s", e)
    finally:
        db.close()
