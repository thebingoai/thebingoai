from typing import Any, Type
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import (
    PostgresConnector,
    dlt_source_for as _postgres_dlt_source_for,
    fingerprint as _postgres_fingerprint,
)
from backend.connectors.mysql import (
    MySQLConnector,
    dlt_source_for as _mysql_dlt_source_for,
    fingerprint as _mysql_fingerprint,
)
from backend.connectors.sql_dlt import SqlExtractionConfig
from backend.connectors.sqlite import SqliteFileConnector
from backend.connectors.data_plane import DataPlaneConnector
from backend.models.database_connection import DatabaseType, DatabaseConnection
from backend.plugins.base import ConnectorRegistration

_CONNECTORS: dict[str, ConnectorRegistration] = {}


def register_connector(reg: ConnectorRegistration) -> None:
    """Called by plugin loader (or core init) to register a connector type."""
    _CONNECTORS[reg.type_id] = reg
    DatabaseType.register(reg.type_id, reg.display_name)


def get_connector_registration(type_id: str) -> ConnectorRegistration | None:
    """Get registration for a type (used by connections.py for hook dispatch)."""
    return _CONNECTORS.get(type_id.lower() if type_id else type_id)


def get_available_types() -> list[dict]:
    """Return metadata for all registered connector types (minus hidden ones)."""
    from backend.config import settings
    hidden = settings.hidden_connector_type_set
    return [
        {
            "id": reg.type_id,
            "display_name": reg.display_name,
            "description": reg.description,
            "default_port": reg.default_port,
            "badge_variant": reg.badge_variant,
            "version": reg.version,
            "card_meta_items": reg.card_meta_items or [],
            "skip_schema_refresh": reg.skip_schema_refresh,
        }
        for reg in _CONNECTORS.values()
        if reg.type_id not in hidden
    ]


def get_connector_for_connection(connection: DatabaseConnection, db_session=None) -> Any:
    """
    Return the appropriate connector for a DatabaseConnection model instance.

    Uses from_connection() classmethod if available on the connector class,
    otherwise falls back to standard host/port/database construction.

    Pass ``db_session`` when the caller already holds one. Plane-backed
    connectors resolve their DataPlane during construction, which needs a
    session; without one they open their own *while the caller still holds its
    own*, doubling peak checkouts on every query. Every ``from_connection``
    override accepts the argument so this can be passed unconditionally.
    """
    db_type_key = connection.db_type.lower() if isinstance(connection.db_type, str) else connection.db_type
    reg = _CONNECTORS.get(db_type_key)
    if not reg:
        raise ValueError(f"No connector registered for type: {connection.db_type}")

    if 'from_connection' in vars(reg.connector_class):
        return reg.connector_class.from_connection(connection, db_session=db_session)

    return reg.connector_class(
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=connection.password,
        ssl_enabled=connection.ssl_enabled,
        ssl_ca_cert=connection.ssl_ca_cert,
    )


def get_connector(
    db_type: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    ssl_enabled: bool = False,
    ssl_ca_cert: str = None
) -> BaseConnector:
    """
    Factory function to create database connector by type string.

    Args:
        db_type: Type of database (e.g. "postgres", "mysql")
        host: Database host
        port: Database port
        database: Database name
        username: Database username
        password: Database password
        ssl_enabled: Enable SSL connection
        ssl_ca_cert: SSL CA certificate (PEM format)

    Returns:
        Instance of appropriate connector class

    Raises:
        ValueError: If database type not supported
    """
    key = db_type if isinstance(db_type, str) else db_type.value if hasattr(db_type, 'value') else str(db_type)
    reg = _CONNECTORS.get(key.lower())

    if reg is None:
        raise ValueError(f"Unsupported database type: {db_type}")

    return reg.connector_class(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        ssl_enabled=ssl_enabled,
        ssl_ca_cert=ssl_ca_cert
    )


# Register core connector types
register_connector(ConnectorRegistration(
    type_id="postgres",
    display_name="PostgreSQL",
    description="Open-source relational database",
    default_port=5432,
    badge_variant="info",
    connector_class=PostgresConnector,
    card_meta_items=["ssl", "table_count", "schema_date"],
    default_scope_hint="org",
    fingerprint=_postgres_fingerprint,
    dlt_source_for=_postgres_dlt_source_for,
    extraction_config_model=SqlExtractionConfig,
))

register_connector(ConnectorRegistration(
    type_id="mysql",
    display_name="MySQL",
    description="Popular open-source relational database",
    default_port=3306,
    badge_variant="warning",
    connector_class=MySQLConnector,
    card_meta_items=["ssl", "table_count", "schema_date"],
    default_scope_hint="org",
    fingerprint=_mysql_fingerprint,
    dlt_source_for=_mysql_dlt_source_for,
    extraction_config_model=SqlExtractionConfig,
))


def _delete_sqlite_file(connection) -> None:
    """Delete a SQLite blob (DataPlane or legacy DO Spaces; skip local/bundled files)."""
    import os
    if not connection.dataset_table_name or os.path.isabs(connection.dataset_table_name):
        return
    try:
        from backend.services.sqlite_blob_storage import delete_blob
        delete_blob(connection)
    except Exception:
        # Connection deletion must never be blocked by a storage error.
        import logging
        logging.getLogger(__name__).warning(
            "sqlite blob delete failed for connection %s", connection.id, exc_info=True,
        )


def _check_sqlite_health(connection) -> dict:
    """Test a SQLite connection, routing the same way queries do.

    Post-migration the blob is deleted and `dataset_table_name` cleared, so the
    blob check would report every migrated connection as broken — mirror
    `SqliteFileConnector.from_connection` and test the DataPlane instead.
    """
    import os
    from backend.database.session import SessionLocal
    from backend.migration.substrate import MigrationJournal

    with SessionLocal() as db:
        migrated = (
            db.query(MigrationJournal)
            .filter(
                MigrationJournal.connection_id == connection.id,
                MigrationJournal.status == "migrated",
            )
            .first()
        )
    if migrated is not None:
        return _test_data_plane(connection)

    if not connection.dataset_table_name:
        return {"success": False, "message": "No SQLite file stored for this connection"}
    if os.path.isabs(connection.dataset_table_name):
        ok = os.path.isfile(connection.dataset_table_name)
    else:
        from backend.services.sqlite_blob_storage import blob_exists
        ok = blob_exists(connection)
    return {
        "success": ok,
        "message": "SQLite file is available" if ok else "SQLite file is missing from storage",
    }


register_connector(ConnectorRegistration(
    type_id="sqlite",
    display_name="SQLite",
    description="Upload a SQLite database file",
    default_port=0,
    badge_variant="secondary",
    connector_class=SqliteFileConnector,
    on_delete=_delete_sqlite_file,
    on_test=_check_sqlite_health,
    skip_schema_refresh=False,
    card_meta_items=["table_count", "schema_date"],
    sql_dialect_hint=(
        "SQLite dialect: use strftime() for dates, LIKE instead of ILIKE, "
        "no :: type casting — use CAST() instead. "
        "Database may have multiple tables with foreign keys."
    ),
))


def _test_data_plane(connection):
    from backend.connectors.data_plane import DataPlaneConnector
    connector = DataPlaneConnector.from_connection(connection)
    try:
        connector.test_connection()
        return {"success": True, "message": "DataPlane is reachable"}
    except Exception as e:
        return {"success": False, "message": str(e)}


register_connector(ConnectorRegistration(
    type_id="data_plane",
    display_name="Data Plane",
    description="Org-level materialized data layer (Parquet + query engine)",
    default_port=0,
    badge_variant="info",
    connector_class=DataPlaneConnector,
    on_test=_test_data_plane,
    skip_schema_refresh=True,
    default_scope_hint="org",
    card_meta_items=["table_count"],
))
