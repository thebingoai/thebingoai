import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.config import settings
from backend.database.session import get_db
from backend.models.database_connection import DatabaseConnection, DatabaseType
from backend.models.team_membership import TeamMembership
from backend.models.team_connection_policy import TeamConnectionPolicy
from backend.models.user import User
from backend.services.dataset_service import (
    create_dataset_sqlite,
    generate_dataset_schema,
    infer_column_types,
    parse_csv,
    parse_excel,
    sanitize_name,
)
from backend.services.schema_discovery import save_schema_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])

_ACCEPTED_EXTENSIONS = {".csv", ".xlsx"}


@router.post("/upload-dataset", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a CSV or Excel file as a permanent PostgreSQL dataset.

    Creates a table in the 'datasets' schema and registers a DatabaseConnection
    of type DATASET, making it queryable by the dashboard agent.
    """
    filename = file.filename or ""
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have an extension (.csv or .xlsx)",
        )
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in _ACCEPTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Accepted: .csv, .xlsx",
        )

    file_bytes = await file.read()
    if len(file_bytes) > settings.dataset_max_file_size:
        max_mb = settings.dataset_max_file_size // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_mb} MB.",
        )

    try:
        df = parse_csv(file_bytes) if ext == ".csv" else parse_excel(file_bytes)
    except Exception as e:
        logger.warning("Failed to parse uploaded file '%s': %s", filename, e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not parse file: {e}",
        )

    if len(df) > settings.dataset_max_rows:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File contains {len(df):,} rows which exceeds the "
                f"{settings.dataset_max_rows:,} row limit."
            ),
        )

    if df.empty or len(df.columns) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File is empty or has no columns.",
        )

    columns = infer_column_types(df)

    base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
    connection_name = name.strip() if name and name.strip() else base_name

    # Create DatabaseConnection record with sentinel values for non-dataset fields
    connection = DatabaseConnection(
        user_id=current_user.id,
        name=connection_name,
        db_type=DatabaseType.DATASET,
        host="internal",
        port=0,
        database="dataset",
        username="dataset",
        source_filename=filename,
    )
    connection.password = "dataset"
    connection.ssl_ca_cert = None

    db.add(connection)
    db.commit()
    db.refresh(connection)

    sanitized = sanitize_name(base_name)

    from backend.services import object_storage as _object_storage

    sqlite_path = create_dataset_sqlite(connection.id, sanitized, columns, df)
    do_spaces_key = f"{settings.do_spaces_base_path}/datasets/sqlite/{connection.id}.sqlite"
    try:
        with open(sqlite_path, 'rb') as f:
            _object_storage.upload_bytes(do_spaces_key, f.read(), content_type="application/x-sqlite3")
    except Exception as e:
        db.delete(connection)
        db.commit()
        logger.error(
            "Dataset SQLite upload failed for connection %s: %s",
            connection.id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload dataset file: {e}",
        )

    connection.dataset_table_name = do_spaces_key
    db.commit()

    row_count = len(df)
    try:
        schema_json = generate_dataset_schema(
            connection_id=connection.id,
            name=connection_name,
            table_name=do_spaces_key,
            columns=columns,
            row_count=row_count,
        )
        schema_path = save_schema_file(connection.id, schema_json)
        connection.schema_json_path = schema_path
        connection.schema_generated_at = datetime.utcnow()
        connection.table_count = 1
        db.commit()
        db.refresh(connection)
    except Exception as e:
        logger.error(
            "Schema generation failed for dataset connection %s: %s",
            connection.id,
            e,
            exc_info=True,
        )

    # Auto-enable for creator's teams (mirrors connections.py governance pattern)
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
        "Dataset upload complete: connection_id=%s, key=%s, rows=%d",
        connection.id,
        do_spaces_key,
        row_count,
    )

    return {
        "id": connection.id,
        "name": connection.name,
        "source_filename": connection.source_filename,
        "table_name": do_spaces_key,
        "row_count": row_count,
        "columns": [{"name": c["name"], "type": c["pg_type"]} for c in columns],
    }
