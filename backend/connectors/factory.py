from typing import Type
from urllib.parse import urlparse
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector
from backend.models.database_connection import DatabaseType, DatabaseConnection

_CONNECTORS: dict[DatabaseType, Type[BaseConnector]] = {
    DatabaseType.POSTGRES: PostgresConnector,
    DatabaseType.MYSQL: MySQLConnector,
}


def get_available_types() -> list[dict]:
    """Return metadata for all registered connector types."""
    types = [
        {
            "id": db_type.value,
            "display_name": cls._db_type_name(),
            "description": cls._description(),
            "default_port": cls._default_port(),
            "badge_variant": cls._badge_variant(),
        }
        for db_type, cls in _CONNECTORS.items()
    ]
    # Dataset type uses the upload endpoint instead of a live connector
    types.append({
        "id": "dataset",
        "display_name": "CSV / Excel",
        "description": "Upload a CSV or Excel file as a queryable dataset",
        "default_port": 0,
        "badge_variant": "secondary",
    })
    return types


def get_connector_for_connection(connection: DatabaseConnection) -> BaseConnector:
    """
    Return the appropriate connector for a DatabaseConnection model instance.

    DATASET connections query the app's own PostgreSQL database (datasets schema),
    so a PostgresConnector is created from settings.database_url rather than
    using the sentinel host/port stored on the record.

    All other types delegate to get_connector().
    """
    if connection.db_type == DatabaseType.DATASET:
        from backend.config import settings
        parsed = urlparse(settings.database_url)
        return PostgresConnector(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/"),
            username=parsed.username,
            password=parsed.password or "",
            ssl_enabled=False,
            ssl_ca_cert=None,
        )
    return get_connector(
        db_type=connection.db_type,
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        password=connection.password,
        ssl_enabled=connection.ssl_enabled,
        ssl_ca_cert=connection.ssl_ca_cert,
    )


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
