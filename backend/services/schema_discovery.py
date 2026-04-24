import json
from typing import Dict, Any
from datetime import datetime
from backend.connectors.base import BaseConnector
import logging

logger = logging.getLogger(__name__)


def discover_schema(connector: BaseConnector) -> Dict[str, Any]:
    """Auto-discover full database schema."""
    logger.info("Starting schema discovery")

    schema_data = {"schemas": {}, "table_names": [], "relationships": []}
    schemas = connector.get_schemas()

    for schema_name in schemas:
        schema_data["schemas"][schema_name] = {"tables": {}}
        tables = connector.get_tables(schema_name)

        for table_name in tables:
            schema_data["table_names"].append(table_name)
            table_schema = connector.get_table_schema(table_name, schema_name)
            foreign_keys = connector.get_foreign_keys(table_name, schema_name)

            schema_data["schemas"][schema_name]["tables"][table_name] = {
                "row_count": table_schema.row_count,
                "columns": table_schema.columns,
            }

            for fk in foreign_keys:
                schema_data["relationships"].append({
                    "from": f"{table_name}.{fk['from_column']}",
                    "to": f"{fk['to_table']}.{fk['to_column']}",
                })

    logger.info(f"Schema discovery completed: {len(schema_data['table_names'])} tables")
    return schema_data


def generate_schema_json(
    connection_id: int,
    connection_name: str,
    db_type: str,
    schema_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate structured schema JSON payload."""
    return {
        "connection_id": connection_id,
        "connection_name": connection_name,
        "db_type": db_type,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schemas": schema_data["schemas"],
        "table_names": schema_data["table_names"],
        "relationships": schema_data["relationships"],
    }


# Map db_type to the DO Spaces category folder for co-located artefacts.
# Unknown types default to "databases".
_DB_TYPE_CATEGORY = {
    "dataset": "datasets",
    "facebook_ads": "facebook_ads",
    "sqlite": "sqlite",
}


def schema_key_for(connection) -> str:
    """Build the DO Spaces key for a connection's schema JSON.

    Co-located with the connection's SQLite (when one exists) under
    `{base_path}/{user_id}/{category}/{uuid}_schema.json`.
    """
    from backend.config import settings

    category = _DB_TYPE_CATEGORY.get(connection.db_type, "databases")
    return (
        f"{settings.do_spaces_base_path}/{connection.user_id}"
        f"/{category}/{connection.uuid}_schema.json"
    )


def save_schema_file(key: str, schema_json: Dict[str, Any]) -> str:
    """Upload schema JSON to DO Spaces at the given key. Returns the key."""
    from backend.services import object_storage

    object_storage.upload_bytes(
        key,
        json.dumps(schema_json, indent=2).encode("utf-8"),
        content_type="application/json",
    )
    logger.info("Schema saved to DO Spaces: %s", key)
    return key


def load_schema_file(key_or_id) -> Dict[str, Any]:
    """Download schema JSON from DO Spaces.

    Accepts either a DO Spaces key (str) or a numeric connection_id (int) —
    the int form looks up the connection's stored `schema_json_path` first,
    so existing callers that pass connection ids keep working.
    """
    from backend.services import object_storage

    if isinstance(key_or_id, int):
        from backend.database.session import SessionLocal
        from backend.models.database_connection import DatabaseConnection

        _db = SessionLocal()
        try:
            conn = _db.query(DatabaseConnection).filter_by(id=key_or_id).first()
            if not conn or not conn.schema_json_path:
                raise FileNotFoundError(f"No schema for connection {key_or_id}")
            key = conn.schema_json_path
        finally:
            _db.close()
    else:
        key = key_or_id

    data = object_storage.download_bytes(key)
    if data is None:
        raise FileNotFoundError(f"Schema not found in DO Spaces: {key}")
    return json.loads(data.decode("utf-8"))


def delete_schema_file(key: str | None) -> bool:
    """Best-effort delete of a schema JSON in DO Spaces."""
    from backend.services import object_storage

    if not key:
        return False
    try:
        object_storage.delete_object(key)
        logger.info("Deleted schema from DO Spaces: %s", key)
        return True
    except Exception as e:
        logger.warning("Failed to delete schema %s: %s", key, e)
        return False


def refresh_schema(
    key: str,
    connector: BaseConnector,
    connection_id: int,
    connection_name: str,
    db_type: str,
) -> str:
    """Re-discover and regenerate schema JSON at the given key."""
    logger.info(f"Refreshing schema at {key}")
    schema_data = discover_schema(connector)
    schema_json = generate_schema_json(connection_id, connection_name, db_type, schema_data)
    return save_schema_file(key, schema_json)
