from typing import Type
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector
from backend.models.database_connection import DatabaseType

_CONNECTORS: dict[DatabaseType, Type[BaseConnector]] = {
    DatabaseType.POSTGRES: PostgresConnector,
    DatabaseType.MYSQL: MySQLConnector,
}


def get_available_types() -> list[dict]:
    """Return metadata for all registered connector types."""
    return [
        {
            "id": db_type.value,
            "display_name": cls._db_type_name(),
            "description": cls._description(),
            "default_port": cls._default_port(),
            "badge_variant": cls._badge_variant(),
        }
        for db_type, cls in _CONNECTORS.items()
    ]


def get_connector(
    db_type: DatabaseType,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    ssl_enabled: bool = False,
    ssl_ca_cert: str = None
) -> BaseConnector:
    """
    Factory function to create database connector.

    Args:
        db_type: Type of database (postgres, mysql)
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
    connector_class = _CONNECTORS.get(db_type)

    if connector_class is None:
        raise ValueError(f"Unsupported database type: {db_type}")

    return connector_class(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
        ssl_enabled=ssl_enabled,
        ssl_ca_cert=ssl_ca_cert
    )
