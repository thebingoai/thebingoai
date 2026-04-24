import json
import os
from typing import Dict, Any
from datetime import datetime
from backend.connectors.base import BaseConnector
from backend.config import settings
import logging

logger = logging.getLogger(__name__)


def discover_schema(connector: BaseConnector) -> Dict[str, Any]:
    """
    Auto-discover full database schema.

    Args:
        connector: Database connector instance

    Returns:
        Dict with schemas, tables, columns, relationships, row counts
    """
    logger.info("Starting schema discovery")

    schema_data = {
        "schemas": {},
        "table_names": [],
        "relationships": []
    }

    # Get all schemas/databases
    schemas = connector.get_schemas()

    for schema_name in schemas:
        schema_data["schemas"][schema_name] = {"tables": {}}

        # Get all tables in schema
        tables = connector.get_tables(schema_name)

        for table_name in tables:
            schema_data["table_names"].append(table_name)

            # Get table schema
            table_schema = connector.get_table_schema(table_name, schema_name)

            # Get foreign keys
            foreign_keys = connector.get_foreign_keys(table_name, schema_name)

            # Store table info
            schema_data["schemas"][schema_name]["tables"][table_name] = {
                "row_count": table_schema.row_count,
                "columns": table_schema.columns
            }

            # Store relationships
            for fk in foreign_keys:
                schema_data["relationships"].append({
                    "from": f"{table_name}.{fk['from_column']}",
                    "to": f"{fk['to_table']}.{fk['to_column']}"
                })

    logger.info(f"Schema discovery completed: {len(schema_data['table_names'])} tables")

    return schema_data


def generate_schema_json(
    connection_id: int,
    connection_name: str,
    db_type: str,
    schema_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate structured schema JSON format.

    Returns:
        Complete schema JSON with metadata
    """
    return {
        "connection_id": connection_id,
        "connection_name": connection_name,
        "db_type": db_type,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "schemas": schema_data["schemas"],
        "table_names": schema_data["table_names"],
        "relationships": schema_data["relationships"]
    }


def save_schema_file(connection_id: int, schema_json: Dict[str, Any]) -> str:
    """
    Save schema JSON to file.

    Args:
        connection_id: Database connection ID
        schema_json: Complete schema JSON

    Returns:
        Path to saved JSON file
    """
    # Ensure schemas directory exists
    schemas_dir = settings.schemas_dir
    os.makedirs(schemas_dir, exist_ok=True)

    # Generate file path
    file_path = os.path.join(schemas_dir, f"{connection_id}_schema.json")

    # Write JSON file
    with open(file_path, 'w') as f:
        json.dump(schema_json, f, indent=2)

    logger.info(f"Schema saved to {file_path}")

    return file_path


def load_schema_file(connection_id: int) -> Dict[str, Any]:
    """
    Load schema JSON from file.

    Args:
        connection_id: Database connection ID

    Returns:
        Schema JSON dict

    Raises:
        FileNotFoundError: If schema file doesn't exist
    """
    file_path = os.path.join(settings.schemas_dir, f"{connection_id}_schema.json")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Schema file not found: {file_path}")

    with open(file_path, 'r') as f:
        return json.load(f)


def refresh_schema(connection_id: int, connector: BaseConnector, connection_name: str, db_type: str) -> str:
    """
    Re-discover and regenerate schema JSON.

    Args:
        connection_id: Database connection ID
        connector: Database connector instance
        connection_name: Connection name
        db_type: Database type

    Returns:
        Path to regenerated schema file
    """
    logger.info(f"Refreshing schema for connection {connection_id}")

    # Discover schema
    schema_data = discover_schema(connector)

    # Generate JSON
    schema_json = generate_schema_json(connection_id, connection_name, db_type, schema_data)

    # Save to file
    file_path = save_schema_file(connection_id, schema_json)

    return file_path


def delete_schema_file(connection_id: int) -> bool:
    """
    Delete schema JSON file.

    Args:
        connection_id: Database connection ID

    Returns:
        True if deleted, False if file didn't exist
    """
    file_path = os.path.join(settings.schemas_dir, f"{connection_id}_schema.json")

    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted schema file: {file_path}")
        return True

    return False
