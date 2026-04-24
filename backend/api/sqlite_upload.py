import logging
import sqlite3
import tempfile
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.config import settings
from backend.connectors.sqlite import SqliteFileConnector, _sqlite_to_pg_type
from backend.database.session import get_db
from backend.models.database_connection import DatabaseConnection
from backend.models.team_membership import TeamMembership
from backend.models.team_connection_policy import TeamConnectionPolicy
from backend.models.user import User
from backend.services.schema_discovery import generate_schema_json, save_schema_file, schema_key_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])

_ACCEPTED_EXTENSIONS = {".sqlite", ".db"}


def _discover_sqlite_schema(db_path: str) -> dict:
    """Discover schema from a SQLite file using PRAGMA commands.

    Returns schema_data dict compatible with generate_schema_json().
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]

        schema_data = {
            "schemas": {"main": {"tables": {}}},
            "table_names": [],
            "relationships": [],
        }

        for table_name in tables:
            schema_data["table_names"].append(table_name)

            # Columns via PRAGMA table_info
            cursor = conn.execute(f'PRAGMA table_info("{table_name}")')
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[1],
                    "type": _sqlite_to_pg_type(row[2]),
                    "nullable": not row[3],
                    "primary_key": bool(row[5]),
                    "foreign_key": None,
                })

            # Row count
            cursor = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]

            schema_data["schemas"]["main"]["tables"][table_name] = {
                "row_count": row_count,
                "columns": columns,
            }

            # Foreign keys via PRAGMA foreign_key_list
            cursor = conn.execute(f'PRAGMA foreign_key_list("{table_name}")')
            for fk_row in cursor.fetchall():
                schema_data["relationships"].append({
                    "from": f"{table_name}.{fk_row[3]}",
                    "to": f"{fk_row[2]}.{fk_row[4]}",
                })

        return schema_data
    finally:
        conn.close()


@router.post("/upload-sqlite", status_code=status.HTTP_201_CREATED)
async def upload_sqlite(
    file: UploadFile = File(...),
    name: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a SQLite database file as a queryable connection.

    Creates a connection of type 'sqlite', stores the file in DO Spaces,
    discovers the schema, and makes it queryable by the dashboard agent.
    """
    filename = file.filename or ""
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have an extension (.sqlite or .db)",
        )
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in _ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Accepted: .sqlite, .db",
        )

    file_bytes = await file.read()
    if len(file_bytes) > settings.dataset_max_file_size:
        max_mb = settings.dataset_max_file_size // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb} MB.",
        )

    # Write to temp file and validate it's a real SQLite database
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    try:
        tmp.write(file_bytes)
        tmp.close()

        try:
            test_conn = sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)
            cursor = test_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            user_tables = [row[0] for row in cursor.fetchall()]
            test_conn.close()
        except sqlite3.DatabaseError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File is not a valid SQLite database.",
            )

        if not user_tables:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="SQLite database contains no user tables.",
            )

        # Discover schema
        schema_data = _discover_sqlite_schema(tmp.name)

        # Create connection record
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        connection_name = name.strip() if name and name.strip() else base_name

        connection = DatabaseConnection(
            user_id=current_user.id,
            name=connection_name,
            db_type="sqlite",
            host="internal",
            port=0,
            database="sqlite",
            username="sqlite",
            source_filename=filename,
        )
        connection.password = "sqlite"
        connection.ssl_ca_cert = None

        db.add(connection)
        db.commit()
        db.refresh(connection)

        # Upload to DO Spaces
        from backend.services import object_storage as _object_storage

        do_spaces_key = f"{settings.do_spaces_base_path}/{current_user.id}/sqlite/{connection.uuid}.sqlite"
        try:
            _object_storage.upload_bytes(do_spaces_key, file_bytes, content_type="application/x-sqlite3")
        except Exception as e:
            db.delete(connection)
            db.commit()
            logger.error(
                "SQLite upload failed for connection %s: %s",
                connection.id, e, exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload SQLite file: {e}",
            )

        connection.dataset_table_name = do_spaces_key
        db.commit()

        # Generate and save schema JSON
        table_count = len(schema_data["table_names"])
        try:
            schema_json = generate_schema_json(
                connection_id=connection.id,
                connection_name=connection_name,
                db_type="sqlite",
                schema_data=schema_data,
            )
            schema_path = save_schema_file(schema_key_for(connection), schema_json)
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = table_count
            db.commit()
            db.refresh(connection)
        except Exception as e:
            logger.error(
                "Schema generation failed for SQLite connection %s: %s",
                connection.id, e, exc_info=True,
            )

        # Kick off background profiling
        if connection.schema_json_path:
            try:
                from backend.tasks.profiling_tasks import profile_connection
                connection.profiling_status = "pending"
                db.commit()
                profile_connection.delay(connection.id)
            except Exception as e:
                logger.error("Failed to queue profiling for SQLite connection %s: %s", connection.id, e)

        # Governance: auto-assign to user's teams
        if settings.enable_governance:
            user_memberships = (
                db.query(TeamMembership)
                .filter(TeamMembership.user_id == current_user.id)
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

        logger.info(
            "SQLite upload complete: connection_id=%s, key=%s, tables=%d",
            connection.id, do_spaces_key, table_count,
        )

        # Build table info for response
        tables_info = []
        for tname, tdata in schema_data["schemas"]["main"]["tables"].items():
            tables_info.append({
                "name": tname,
                "row_count": tdata["row_count"],
                "column_count": len(tdata["columns"]),
            })

        return {
            "id": connection.id,
            "name": connection.name,
            "source_filename": connection.source_filename,
            "table_count": table_count,
            "tables": tables_info,
        }

    finally:
        os.unlink(tmp.name)
