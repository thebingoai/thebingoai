from typing import Any, Type
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector
from backend.connectors.sqlite import SqliteFileConnector
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
    """Return metadata for all registered connector types."""
    return [
        {
            "id": reg.type_id,
            "display_name": reg.display_name,
            "description": reg.description,
            "default_port": reg.default_port,
            "badge_variant": reg.badge_variant,
            "version": reg.version,
            "card_meta_items": reg.card_meta_items or [],
        }
        for reg in _CONNECTORS.values()
    ]


def get_connector_for_connection(connection: DatabaseConnection) -> Any:
    """
    Return the appropriate connector for a DatabaseConnection model instance.

    Uses from_connection() classmethod if available on the connector class,
    otherwise falls back to standard host/port/database construction.
    """
    db_type_key = connection.db_type.lower() if isinstance(connection.db_type, str) else connection.db_type
    reg = _CONNECTORS.get(db_type_key)
    if not reg:
        raise ValueError(f"No connector registered for type: {connection.db_type}")

    if 'from_connection' in vars(reg.connector_class):
        return reg.connector_class.from_connection(connection)

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
))

register_connector(ConnectorRegistration(
    type_id="mysql",
    display_name="MySQL",
    description="Popular open-source relational database",
    default_port=3306,
    badge_variant="warning",
    connector_class=MySQLConnector,
    card_meta_items=["ssl", "table_count", "schema_date"],
))


def _delete_sqlite_file(connection) -> None:
    """Delete a SQLite file from DO Spaces (skip local/bundled files)."""
    import os
    if connection.dataset_table_name and not os.path.isabs(connection.dataset_table_name):
        from backend.services import object_storage
        object_storage.delete_object(connection.dataset_table_name)


def _check_sqlite_health(connection) -> bool:
    """Check whether a SQLite connection's file exists (local or DO Spaces)."""
    import os
    if not connection.dataset_table_name:
        return False
    if os.path.isabs(connection.dataset_table_name):
        return os.path.isfile(connection.dataset_table_name)
    from backend.services import object_storage
    return object_storage.object_exists(connection.dataset_table_name)


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
