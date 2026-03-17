from typing import Any, Type
from backend.connectors.base import BaseConnector
from backend.connectors.postgres import PostgresConnector
from backend.connectors.mysql import MySQLConnector
from backend.connectors.sqlite_connector import SQLiteConnector
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


def _get_sqlite_connector_for_dataset(connection: DatabaseConnection) -> SQLiteConnector:
    """
    Download (or use cached) SQLite file from DO Spaces and return a SQLiteConnector.

    The DO Spaces key is stored in connection.dataset_table_name.
    The file is cached locally at {settings.dataset_cache_dir}/{connection.id}.sqlite
    for up to 1 hour.
    """
    import os
    import time
    from backend.services import object_storage
    from backend.config import settings

    do_spaces_key = connection.dataset_table_name
    cache_dir = settings.dataset_cache_dir
    cache_path = os.path.join(cache_dir, f"{connection.id}.sqlite")

    # Check if cache is fresh (less than 1 hour old)
    cache_valid = (
        os.path.exists(cache_path)
        and os.path.getmtime(cache_path) > time.time() - 3600
    )

    if not cache_valid:
        # Download from DO Spaces
        data = object_storage.download_bytes(do_spaces_key)
        if data is None:
            raise FileNotFoundError(
                f"SQLite file not found in DO Spaces: {do_spaces_key}"
            )

        # Ensure cache directory exists
        os.makedirs(cache_dir, exist_ok=True)

        # Atomic write: write to .tmp then rename
        tmp_path = cache_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.rename(tmp_path, cache_path)

    return SQLiteConnector(cache_path)


def get_connector_for_connection(connection: DatabaseConnection) -> Any:
    """
    Return the appropriate connector for a DatabaseConnection model instance.

    DATASET connections use SQLiteConnector backed by a SQLite file stored in DO Spaces.
    The file is downloaded to a local cache and served from there.

    All other types delegate to get_connector().
    """
    if str(connection.db_type).upper() == DatabaseType.DATASET.name:
        return _get_sqlite_connector_for_dataset(connection)
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
