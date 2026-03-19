from typing import Any, Type
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector
from backend.models.database_connection import DatabaseType, DatabaseConnection
from backend.plugins.base import ConnectorRegistration

_CONNECTORS: dict[str, ConnectorRegistration] = {}


def register_connector(reg: ConnectorRegistration) -> None:
    """Called by plugin loader (or core init) to register a connector type."""
    _CONNECTORS[reg.type_id] = reg
    DatabaseType.register(reg.type_id, reg.display_name)


def get_connector_registration(type_id: str) -> ConnectorRegistration | None:
    """Get registration for a type (used by connections.py for hook dispatch)."""
    return _CONNECTORS.get(type_id)


def get_available_types() -> list[dict]:
    """Return metadata for all registered connector types."""
    return [
        {
            "id": reg.type_id,
            "display_name": reg.display_name,
            "description": reg.description,
            "default_port": reg.default_port,
            "badge_variant": reg.badge_variant,
        }
        for reg in _CONNECTORS.values()
    ]


def get_connector_for_connection(connection: DatabaseConnection) -> Any:
    """
    Return the appropriate connector for a DatabaseConnection model instance.

    Uses from_connection() classmethod if available on the connector class,
    otherwise falls back to standard host/port/database construction.
    """
    reg = _CONNECTORS.get(connection.db_type)
    if not reg:
        raise ValueError(f"No connector registered for type: {connection.db_type}")

    if hasattr(reg.connector_class, 'from_connection'):
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
    reg = _CONNECTORS.get(db_type if isinstance(db_type, str) else db_type.value if hasattr(db_type, 'value') else str(db_type))

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
))

register_connector(ConnectorRegistration(
    type_id="mysql",
    display_name="MySQL",
    description="Popular open-source relational database",
    default_port=3306,
    badge_variant="warning",
    connector_class=MySQLConnector,
))
