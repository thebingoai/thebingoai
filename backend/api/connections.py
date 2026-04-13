from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.models.team_membership import TeamMembership
from backend.models.team_connection_policy import TeamConnectionPolicy
from backend.schemas.connection import (
    ConnectionCreate, ConnectionUpdate, ConnectionResponse,
    ConnectionTestResponse, SchemaRefreshResponse, ConnectorTypeResponse,
    SchemaResponse
)
from backend.connectors.factory import get_connector, get_available_types, get_connector_registration
from backend.services.schema_discovery import (
    discover_schema, generate_schema_json, save_schema_file,
    refresh_schema, delete_schema_file, load_schema_file
)
from backend.config import settings
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


def _invalidate_dashboard_caches_for_connection(
    connection_id: int, user_id: str, db: Session,
) -> int:
    """Mark all dashboard caches as 'stale' that reference the given connection.

    Returns the number of dashboards marked stale.
    """
    from backend.models.dashboard import Dashboard

    dashboards = db.query(Dashboard).filter(
        Dashboard.user_id == user_id,
        Dashboard.cache_status.in_(["ready", "building"]),
    ).all()

    count = 0
    for dashboard in dashboards:
        for widget in (dashboard.widgets or []):
            ds = widget.get("dataSource")
            if ds and ds.get("connectionId") == connection_id:
                dashboard.cache_status = "stale"
                count += 1
                break

    if count:
        db.flush()
        logger.info(
            "Marked %d dashboard cache(s) as stale for connection %d",
            count, connection_id,
        )
    return count


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
                connection.db_type,
                schema_data
            )
            schema_path = save_schema_file(connection.id, schema_json)

            # Update connection with schema info
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = len(schema_data["table_names"])
            db.commit()
            db.refresh(connection)

        # Kick off background profiling now that schema is available
        from backend.tasks.profiling_tasks import profile_connection
        connection.profiling_status = "pending"
        db.commit()
        profile_connection.delay(connection.id)

    except Exception as e:
        # Log error but don't fail connection creation
        # Schema can be generated later via refresh endpoint
        logger.error("Schema discovery failed for connection %s: %s", connection.id, e, exc_info=True)

    db.refresh(connection)
    logger.info("Connection '%s' (id=%s) created successfully", connection.name, connection.id)
    return connection


@router.get("", response_model=List[ConnectionResponse])
async def list_connections(
    include_ephemeral: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all database connections for current user.

    By default, ephemeral datasets (created via chat uploads) are hidden.
    Pass include_ephemeral=true to include them.
    """
    query = db.query(DatabaseConnection).filter(
        DatabaseConnection.user_id == current_user.id
    )
    if not include_ephemeral:
        query = query.filter(DatabaseConnection.is_ephemeral == False)  # noqa: E712

    return query.all()


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


@router.get("/types/{type_id}/changelog")
async def get_connector_changelog(type_id: str):
    """Return changelog for a connector type."""
    from backend.api.health import APP_VERSION
    from backend.plugins.loader import get_plugin_for_connector
    from pathlib import Path
    import importlib

    reg = get_connector_registration(type_id)
    if not reg:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown connector type: {type_id}")

    plugin = get_plugin_for_connector(type_id)
    if plugin is None:
        return {
            "changelog": "Built-in connector. See application release notes.",
            "version": reg.version or APP_VERSION,
        }

    # Resolve CHANGELOG.md from plugin's package directory
    try:
        mod = importlib.import_module(plugin.__class__.__module__)
        pkg_dir = Path(mod.__file__).parent
        changelog_path = pkg_dir / "CHANGELOG.md"
        if changelog_path.exists():
            return {
                "changelog": changelog_path.read_text(encoding="utf-8"),
                "version": reg.version or plugin.version,
            }
    except Exception:
        pass

    return {
        "changelog": "No changelog available.",
        "version": reg.version or plugin.version,
    }


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


@router.post("/test-connection-write", response_model=ConnectionTestResponse)
async def test_unsaved_write_access(
    request: ConnectionCreate,
    current_user: User = Depends(get_current_user)
):
    """Test write access (roles/bigquery.dataEditor) for an unsaved BigQuery connection."""
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
        has_write = connector.test_write_access()
        connector.close()
        if has_write:
            return ConnectionTestResponse(success=True, message="Write access granted")
        return ConnectionTestResponse(success=False, message="roles/bigquery.dataEditor not granted on this project or dataset")
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

    # Invalidate dashboard caches that use this connection
    _invalidate_dashboard_caches_for_connection(connection_id, current_user.id, db)

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

    # Invalidate dashboard caches that use this connection
    _invalidate_dashboard_caches_for_connection(connection_id, current_user.id, db)

    # Run type-specific delete hook if registered (e.g., dataset cleanup)
    reg = get_connector_registration(connection.db_type)
    if reg and reg.on_delete:
        try:
            reg.on_delete(connection)
        except Exception as e:
            logger.warning("on_delete hook failed for connection %s: %s", connection.id, e)

    # Delete schema and context JSON files
    delete_schema_file(connection_id)
    from backend.services.connection_context import delete_context_file
    delete_context_file(connection_id)

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

    reg = get_connector_registration(connection.db_type)
    if reg and reg.on_test:
        try:
            result = reg.on_test(connection)
            return ConnectionTestResponse(**result)
        except Exception as e:
            return ConnectionTestResponse(success=False, message=str(e))

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


@router.post("/{connection_id}/test-write", response_model=ConnectionTestResponse)
async def test_write_access(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test write access (roles/bigquery.dataEditor) for a saved connection."""
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
            password=connection.password,
            ssl_enabled=connection.ssl_enabled,
            ssl_ca_cert=connection.ssl_ca_cert
        )
        has_write = connector.test_write_access()
        connector.close()
        if has_write:
            return ConnectionTestResponse(success=True, message="Write access granted")
        return ConnectionTestResponse(success=False, message="roles/bigquery.dataEditor not granted on this project or dataset")
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

    reg = get_connector_registration(connection.db_type)
    if reg and reg.skip_schema_refresh:
        if reg.on_refresh_schema:
            try:
                result = reg.on_refresh_schema(connection)
                return SchemaRefreshResponse(**result)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Schema refresh failed: {str(e)}",
                )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema refresh is not supported for {reg.display_name} connections.",
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
                connection.db_type
            )

            # Load refreshed schema to get table count
            schema_json = load_schema_file(connection.id)

            # Update connection timestamp and table count
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = len(schema_json["table_names"])

            # Re-trigger profiling since schema changed
            from backend.tasks.profiling_tasks import profile_connection
            connection.profiling_status = "pending"
            db.commit()
            profile_connection.delay(connection.id)

            db.refresh(connection)

            return SchemaRefreshResponse(
                success=True,
                message="Schema refreshed successfully. Profiling will run in the background.",
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


@router.get("/{connection_id}/profiling-status")
async def get_profiling_status(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get profiling status for a connection (used for polling during profiling)."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    return {
        "status": connection.profiling_status,
        "progress": connection.profiling_progress,
        "error": connection.profiling_error,
        "started_at": connection.profiling_started_at.isoformat() if connection.profiling_started_at else None,
        "completed_at": connection.profiling_completed_at.isoformat() if connection.profiling_completed_at else None,
    }


@router.post("/{connection_id}/reprofile")
async def reprofile_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger re-profiling for a connection."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.profiling_status == "in_progress":
        raise HTTPException(status_code=400, detail="Profiling is already in progress")

    if not connection.schema_json_path:
        raise HTTPException(status_code=400, detail="Schema has not been discovered yet. Refresh the schema first.")

    from backend.tasks.profiling_tasks import profile_connection
    connection.profiling_status = "pending"
    connection.profiling_error = None
    connection.profiling_progress = None
    db.commit()
    profile_connection.delay(connection.id)

    return {"message": "Profiling queued", "status": "pending"}


@router.get("/{connection_id}/context")
async def get_connection_context(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the data context for a connection (used by the dashboard agent)."""
    connection = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == current_user.id,
    ).first()

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.profiling_status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Data context is not ready. Current profiling status: {connection.profiling_status}",
        )

    from backend.services.connection_context import load_context_file
    try:
        return load_context_file(connection_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Context file not found. Try re-profiling the connection.")
