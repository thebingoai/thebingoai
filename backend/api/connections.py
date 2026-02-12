from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.connection import (
    ConnectionCreate, ConnectionUpdate, ConnectionResponse,
    ConnectionTestResponse, SchemaRefreshResponse
)
from backend.connectors.factory import get_connector
from backend.services.schema_discovery import (
    discover_schema, generate_schema_json, save_schema_file,
    refresh_schema, delete_schema_file
)
from datetime import datetime

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
    1. Test connection (5s timeout)
    2. Save connection to database
    3. Auto-discover full schema
    4. Save schema as JSON to data/schemas/{id}_schema.json
    5. Update connection with schema path and timestamp
    """
    # Test connection before saving
    try:
        connector = get_connector(
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password
        )
        connector.test_connection()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection test failed: {str(e)}"
        )

    # Create connection (without schema info yet)
    connection = DatabaseConnection(
        user_id=current_user.id,
        **request.model_dump()
    )

    db.add(connection)
    db.commit()
    db.refresh(connection)

    # Auto-discover schema
    try:
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
        db.commit()
        db.refresh(connection)

    except Exception as e:
        # Log error but don't fail connection creation
        # Schema can be generated later via refresh endpoint
        import logging
        logging.error(f"Schema discovery failed: {str(e)}")

    finally:
        connector.close()

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

    # Delete schema JSON file
    delete_schema_file(connection_id)

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

    try:
        connector = get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
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

    try:
        with get_connector(
            db_type=connection.db_type,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password
        ) as connector:
            schema_path = refresh_schema(
                connection.id,
                connector,
                connection.name,
                connection.db_type.value
            )

            # Update connection timestamp
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
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
