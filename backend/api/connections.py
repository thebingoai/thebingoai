from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from backend.database.session import get_db
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection, ProfilingStatus
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
    refresh_schema, delete_schema_file, load_schema_file, schema_key_for,
)
from backend.config import settings
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)


def _schema_item_count(db_type: str, schema_data: dict) -> int:
    """Return the appropriate count to store in table_count for a given connector type.

    Connectors that expose 'dataset_count' in their card_meta_items (e.g. BigQuery)
    should display the number of top-level schemas (datasets), not the total table count.
    """
    reg = get_connector_registration(db_type)
    if reg and "dataset_count" in (reg.card_meta_items or []):
        return len(schema_data.get("schemas", {}))
    return len(schema_data.get("table_names", []))


def _find_connection(db: Session, key, current_user):
    """Look up a connection by either its UUID or its numeric id.

    Accepts str (FastAPI path params) or int (internal callers / tests).
    Returns the connection if visible to ``current_user`` under the Phase 3
    collaborative-workspace rules:

      - Same-org members see every connection in their org.
      - Users without an ``org_id`` (legacy / community) fall back to the
        previous owner-only behaviour.

    Mutating routes still need to call ``governance.require(...)`` separately
    to enforce per-org-admin / owner mutate semantics.
    """
    key_str = str(key)
    q = db.query(DatabaseConnection)
    if key_str.isdigit():
        q = q.filter(DatabaseConnection.id == int(key_str))
    else:
        q = q.filter(DatabaseConnection.uuid == key_str)

    org_id = getattr(current_user, "org_id", None)
    if org_id is not None:
        # Visible if: row already carries org_id, OR row's owner currently
        # belongs to this org (covers pre-Phase-3 rows that never recorded
        # org_id directly).
        from sqlalchemy import or_
        q = q.outerjoin(User, DatabaseConnection.user_id == User.id).filter(
            or_(
                DatabaseConnection.org_id == org_id,
                User.org_id == org_id,
            )
        )
    else:
        q = q.filter(DatabaseConnection.user_id == current_user.id)
    return q.first()


def _governance_require_mutate_connection(current_user, connection) -> None:
    """Phase 3 inline guard for PATCH/PUT/DELETE on a connection.

    The collaborative-workspace policy lets any org-mate see a connection,
    but only the owner, a per-org admin, or a bingo_admin may mutate it.
    """
    from backend.governance.contract import require as governance_require
    governance_require(
        user=current_user,
        action="update",
        resource={
            "type": "connection",
            "org_id": str(connection.org_id) if connection.org_id else None,
            "owner_user_id": str(connection.user_id) if connection.user_id else None,
        },
    )


router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(
    request: ConnectionCreate,
    force: bool = False,
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

    from backend.governance.contract import (
        find_duplicate_connection,
        require as governance_require,
    )
    governance_require(
        user=current_user,
        action="create",
        resource={"type": "connection", "db_type": request.db_type},
    )

    if not force:
        existing_id = find_duplicate_connection(
            user=current_user,
            connection_payload=request.model_dump(),
        )
        if existing_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": (
                        "An organization-scoped connection with the same identity "
                        "already exists. Pass ?force=true to create a duplicate."
                    ),
                    "existing_connection_id": existing_id,
                },
            )

    # Create connection (without schema info yet)
    # password and ssl_ca_cert use hybrid_property setters and cannot be passed
    # as constructor kwargs (SQLAlchemy only accepts mapped column attribute names)
    data = request.model_dump()
    password = data.pop('password')
    ssl_ca_cert = data.pop('ssl_ca_cert', None)

    connection = DatabaseConnection(
        user_id=current_user.id,
        org_id=current_user.org_id,
        owner_scope_kind="user",
        owner_scope_id=current_user.id,
        **data,
    )
    connection.password = password
    connection.ssl_ca_cert = ssl_ca_cert

    db.add(connection)
    db.commit()
    db.refresh(connection)

    from backend.governance.contract import emit_resource_created
    emit_resource_created(
        resource_type="connection",
        resource=connection,
        creator_user=current_user,
    )

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

    db.refresh(connection)

    # Materialize plugin-shipped pipeline + transform templates for this connector type.
    # Idempotent — safe even if a later retry hits the same connection.
    reg = get_connector_registration(connection.db_type)
    if reg and (reg.pipeline_templates or reg.transform_templates):
        try:
            from backend.services.template_materializer import materialize_templates_for_connection
            materialize_templates_for_connection(connection, reg, db)
            db.commit()
            db.refresh(connection)
        except Exception as e:
            logger.warning(
                "Template materialization failed for connection %s (%s): %s",
                connection.id, connection.db_type, e,
            )
            db.rollback()

    # Auto-discover schema for all connector types except BigQuery (too many datasets)
    if request.db_type != "bigquery":
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
                schema_path = save_schema_file(schema_key_for(connection), schema_json)

                connection.schema_json_path = schema_path
                connection.schema_generated_at = datetime.utcnow()
                connection.table_count = _schema_item_count(connection.db_type, schema_data)
                db.commit()
                db.refresh(connection)

            from backend.tasks.profiling_tasks import profile_connection
            connection.profiling_status = ProfilingStatus.PENDING.value
            db.commit()
            profile_connection.delay(connection.id)

        except Exception as e:
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
    """List database connections visible to the current user.

    Phase 3 collaborative workspace: returns every connection in the caller's
    org. Users without an `org_id` (legacy / community standalone) still see
    only their own. Ephemeral datasets (chat uploads) are hidden unless
    explicitly requested.
    """
    query = db.query(DatabaseConnection)
    if current_user.org_id is not None:
        from sqlalchemy import or_
        query = query.outerjoin(User, DatabaseConnection.user_id == User.id).filter(
            or_(
                DatabaseConnection.org_id == current_user.org_id,
                User.org_id == current_user.org_id,
            )
        )
    else:
        query = query.filter(DatabaseConnection.user_id == current_user.id)
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
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific database connection."""
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    return connection


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: str,
    request: ConnectionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a database connection."""
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    _governance_require_mutate_connection(current_user, connection)

    # Update fields
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(connection, field, value)

    db.commit()
    db.refresh(connection)

    return connection


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str,
    cascade: bool = Query(False, description="If true, also delete dependent pipelines (and their run history)."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a database connection and its cached schema.

    When ``cascade=false`` (default), returns HTTP 409 ``connection_in_use``
    listing dependent pipelines so the UI can re-confirm. When ``cascade=true``,
    dependent pipelines (and their PipelineRun / DltPipelineState rows) are
    deleted first via ``resource_lifecycle.delete_pipeline``.
    """
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    _governance_require_mutate_connection(current_user, connection)

    # Delegates dependency check + optional cascade to the lifecycle helper.
    # Re-raises the helper's RuntimeError as the existing 409 payload so the
    # frontend's error parser is unchanged.
    from backend.models.pipeline import Pipeline
    from backend.services.resource_lifecycle import guard_connection_delete
    try:
        guard_connection_delete(connection.id, db, cascade=cascade)
    except RuntimeError:
        blocking = db.query(Pipeline.id, Pipeline.name).filter(
            Pipeline.source_connection_id == connection.id
        ).all()
        pipeline_list = [{"id": p.id, "name": p.name} for p in blocking]
        names_preview = ", ".join(p["name"] for p in pipeline_list[:3])
        if len(pipeline_list) > 3:
            names_preview += f", +{len(pipeline_list) - 3} more"
        raise HTTPException(
            status_code=409,
            detail={
                "code": "connection_in_use",
                "message": (
                    f"This connection is used by {len(pipeline_list)} pipeline"
                    f"{'s' if len(pipeline_list) != 1 else ''} ({names_preview})."
                ),
                "pipelines": pipeline_list,
            },
        )

    # Run type-specific delete hook if registered (e.g., dataset cleanup)
    reg = get_connector_registration(connection.db_type)
    if reg and reg.on_delete:
        try:
            reg.on_delete(connection)
        except Exception as e:
            logger.warning("on_delete hook failed for connection %s: %s", connection.id, e)

    # Delete schema JSON file; connection context lives on the row and is removed by the DELETE below.
    delete_schema_file(connection.schema_json_path)

    # Remove any team connection policies first to avoid FK violations
    db.query(TeamConnectionPolicy).filter(
        TeamConnectionPolicy.connection_id == connection.id
    ).delete()

    # Delete connection from database
    db.delete(connection)
    db.commit()


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test a database connection."""
    connection = _find_connection(db, connection_id, current_user)

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
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test write access (roles/bigquery.dataEditor) for a saved connection."""
    connection = _find_connection(db, connection_id, current_user)

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
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh cached schema for a database connection.

    Re-discovers full schema and regenerates JSON file.
    Useful when database structure changes.
    """
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    _governance_require_mutate_connection(current_user, connection)

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
                schema_key_for(connection),
                connector,
                connection.id,
                connection.name,
                connection.db_type,
            )

            # Load refreshed schema to get table count
            schema_json = load_schema_file(schema_path)

            # Update connection timestamp and table count
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = _schema_item_count(connection.db_type, schema_json)

            # Re-trigger profiling since schema changed
            from backend.tasks.profiling_tasks import profile_connection
            connection.profiling_status = ProfilingStatus.PENDING.value
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
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get cached schema JSON for a database connection.

    Returns the full schema including schemas, tables, columns, and relationships.
    Returns 404 if schema has not been generated yet.
    """
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if not connection.schema_json_path:
        raise HTTPException(
            status_code=404,
            detail="Schema not yet generated. Create the connection or use the refresh endpoint."
        )
    try:
        return load_schema_file(connection.schema_json_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Schema not yet generated. Create the connection or use the refresh endpoint."
        )


@router.get("/{connection_id}/profiling-status")
async def get_profiling_status(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get profiling status for a connection (used for polling during profiling)."""
    connection = _find_connection(db, connection_id, current_user)

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
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger re-profiling for a connection."""
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    _governance_require_mutate_connection(current_user, connection)

    if connection.profiling_status == "in_progress":
        raise HTTPException(status_code=400, detail="Profiling is already in progress")

    if not connection.schema_json_path:
        raise HTTPException(status_code=400, detail="Schema has not been discovered yet. Refresh the schema first.")

    from backend.tasks.profiling_tasks import profile_connection
    connection.profiling_status = ProfilingStatus.PENDING.value
    connection.profiling_error = None
    connection.profiling_progress = None
    db.commit()
    profile_connection.delay(connection.id)

    return {"message": "Profiling queued", "status": "pending"}


@router.get("/{connection_id}/context")
async def get_connection_context(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the data context for a connection (used by the dashboard agent)."""
    connection = _find_connection(db, connection_id, current_user)

    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    if connection.profiling_status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Data context is not ready. Current profiling status: {connection.profiling_status}",
        )

    from backend.services.connection_context import load_connection_context
    ctx = load_connection_context(db, connection.id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Context not found. Try re-profiling the connection.")
    return ctx
