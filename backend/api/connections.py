from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection, DatabaseType
from backend.models.team_membership import TeamMembership
from backend.models.team_connection_policy import TeamConnectionPolicy
from backend.schemas.connection import (
    ConnectionCreate, ConnectionUpdate, ConnectionResponse,
    ConnectionTestResponse, SchemaRefreshResponse, ConnectorTypeResponse,
    SchemaResponse
)
from backend.connectors.factory import get_connector, get_available_types
from backend.services.schema_discovery import (
    discover_schema, generate_schema_json, save_schema_file,
    refresh_schema, delete_schema_file, load_schema_file
)
from backend.config import settings
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    request: ConnectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new database connection with automatic schema discovery.

    Flow:
    1. Save connection to database
    2. Auto-discover full schema (non-blocking, can fail silently)
    3. Save schema as JSON to data/schemas/{id}_schema.json
    4. Update connection with schema path and timestamp
    """
    logger.info("Creating connection '%s' (type=%s, host=%s, port=%s, db=%s, ssl=%s)",
        request.name, request.db_type, request.host, request.port, request.database, request.ssl_enabled)

    # Create connection (without schema info yet)
    # password and ssl_ca_cert use hybrid_property setters and cannot be passed
    # as constructor kwargs (SQLAlchemy only accepts mapped column attribute names)
    data = request.model_dump()
    password = data.pop('password')
    ssl_ca_cert = data.pop('ssl_ca_cert', None)

    connection = DatabaseConnection(user_id=current_user.id, **data)
    connection.password = password
    connection.ssl_ca_cert = ssl_ca_cert

    db.add(connection)
    db.commit()
    db.refresh(connection)

    # Auto-enable connection for creator's teams (governance only)
    if settings.enable_governance:
        user_memberships = db.query(TeamMembership).filter(
            TeamMembership.user_id == current_user.id
        ).all()
        for membership in user_memberships:
            db.add(TeamConnectionPolicy(
                id=str(uuid.uuid4()),
                team_id=membership.team_id,
                connection_id=connection.id,
            ))
        if user_memberships:
            db.commit()

    # Auto-discover schema
    try:
        with get_connector(
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
            ssl_enabled=request.ssl_enabled,
            ssl_ca_cert=request.ssl_ca_cert
        ) as connector:
            schema_data = discover_schema(connector)
            schema_json = generate_schema_json(
                connection.id,
                connection.name,
                connection.db_type.value,
                schema_data
            )
            schema_path = save_schema_file(connection.id, schema_json)

            # Update connection with schema info
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = len(schema_data["table_names"])
            db.commit()
            db.refresh(connection)

    except Exception as e:
        # Log error but don't fail connection creation
        # Schema can be generated later via refresh endpoint
        logger.error("Schema discovery failed for connection %s: %s", connection.id, e, exc_info=True)

    logger.info("Connection '%s' (id=%s) created successfully", connection.name, connection.id)
    return connection


@router.get("", response_model=List[ConnectionResponse])
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all database connections for current user."""
    connections = db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == current_user.id
    ).all()

    return connections


@router.get("/org", response_model=List[ConnectionResponse])
async def list_org_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all connections in the current user's organization (for policy management)."""
    if not current_user.org_id:
        return []
    org_user_ids = [
        row.id for row in db.query(User.id).filter(User.org_id == current_user.org_id).all()
    ]
    connections = db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id.in_(org_user_ids)
    ).all()
    return connections


@router.get("/types", response_model=list[ConnectorTypeResponse])
async def get_connector_types():
    """Return metadata for all available database connector types."""
    return get_available_types()


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_unsaved_connection(
    request: ConnectionCreate,
    current_user: User = Depends(get_current_user)
):
    """Test a database connection without saving it."""
    try:
        connector = get_connector(
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
            ssl_enabled=request.ssl_enabled,
            ssl_ca_cert=request.ssl_ca_cert
        )
        connector.test_connection()
        connector.close()
        return ConnectionTestResponse(success=True, message="Connection successful")
    except Exception as e:
        return ConnectionTestResponse(success=False, message=str(e))


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific database connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    return connection


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: int,
    request: ConnectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a database connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Update fields
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(connection, field, value)

    db.commit()
    db.refresh(connection)

    return connection


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a database connection and its cached schema."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Drop the underlying PostgreSQL table for dataset connections
    if connection.db_type == DatabaseType.DATASET and connection.dataset_table_name:
        from backend.services.dataset_service import drop_dataset_table
        drop_dataset_table(connection.dataset_table_name)

    # Delete schema JSON file
    delete_schema_file(connection_id)

    # Remove any team connection policies first to avoid FK violations
    db.query(TeamConnectionPolicy).filter(
        TeamConnectionPolicy.connection_id == connection_id
    ).delete()

    # Delete connection from database
    db.delete(connection)
    db.commit()


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a database connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.db_type == DatabaseType.DATASET:
        return ConnectionTestResponse(success=True, message="Dataset connection — no external host to test")

    try:
        connector = get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password,
            ssl_enabled=connection.ssl_enabled,
            ssl_ca_cert=connection.ssl_ca_cert
        )
        connector.test_connection()
        connector.close()

        return ConnectionTestResponse(success=True, message="Connection successful")
    except Exception as e:
        return ConnectionTestResponse(success=False, message=str(e))


@router.post("/{connection_id}/refresh-schema", response_model=SchemaRefreshResponse)
async def refresh_connection_schema(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh cached schema for a database connection.

    Re-discovers full schema and regenerates JSON file.
    Useful when database structure changes.
    """
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.db_type == DatabaseType.DATASET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schema refresh is not supported for dataset connections.",
        )

    try:
        with get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password,
            ssl_enabled=connection.ssl_enabled,
            ssl_ca_cert=connection.ssl_ca_cert
        ) as connector:
            schema_path = refresh_schema(
                connection.id,
                connector,
                connection.name,
                connection.db_type.value
            )

            # Load refreshed schema to get table count
            schema_json = load_schema_file(connection.id)

            # Update connection timestamp and table count
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = len(schema_json["table_names"])
            db.commit()
            db.refresh(connection)

            return SchemaRefreshResponse(
                success=True,
                message="Schema refreshed successfully",
                schema_generated_at=connection.schema_generated_at
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema refresh failed: {str(e)}"
        )


@router.get("/{connection_id}/schema", response_model=SchemaResponse)
async def get_connection_schema(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cached schema JSON for a database connection.

    Returns the full schema including schemas, tables, columns, and relationships.
    Returns 404 if schema has not been generated yet.
    """
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        schema_json = load_schema_file(connection_id)
        return schema_json
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Schema not yet generated. Create the connection or use the refresh endpoint."
        )
