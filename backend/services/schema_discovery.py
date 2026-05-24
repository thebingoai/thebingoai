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


def augment_schema_with_pipelines(schema_data: Dict[str, Any], connection) -> Dict[str, Any]:
    """For connectors that own managed pipelines (e.g. bigquery_ga4 -> bronze
    + dedup view), inject the materialized target table into schema_data so the
    dashboard agent + briefing agent can see + plan against the deduped
    output, not just the raw source schema.

    No-op for connector types without managed pipelines. Safe to call after
    any discover_schema(). Mutates and returns *schema_data*.
    """
    # Gate strictly on db_type so other connectors (postgres, mysql, csv,
    # notion, facebook_ads) are untouched.
    if connection.db_type != "bigquery_ga4":
        return schema_data

    from backend.database.session import SessionLocal
    from backend.data_plane.scope import OwnerScope
    from backend.models.pipeline import Pipeline
    from backend.services.data_plane_service import get_default_plane

    db = SessionLocal()
    try:
        pipelines = db.query(Pipeline).filter(
            Pipeline.source_connection_id == connection.id,
        ).all()
        if not pipelines:
            return schema_data

        pipeline_tables: Dict[str, Any] = {}
        for p in pipelines:
            try:
                scope = OwnerScope(kind=p.owner_scope_kind, id=p.owner_scope_id)
                plane = get_default_plane(scope, db)
                arrow_schema = plane.get_schema(scope, p.target_table)
            except Exception:
                # Materialised yet? Skip until first run completes; refresh
                # will pick it up next time.
                logger.warning(
                    "augment_schema_with_pipelines: plane.get_schema failed for "
                    "%s (pipeline %s) -- skipping",
                    p.target_table, p.id, exc_info=True,
                )
                continue
            from backend.tasks.profiling_tasks import _arrow_type_canonical
            columns = []
            for field in arrow_schema:
                columns.append({
                    "name": field.name,
                    "type": _arrow_type_canonical(field.type),
                    "nullable": field.nullable,
                    "primary_key": False,
                })
            pipeline_tables[p.target_table] = {
                "row_count": 0,
                "columns": columns,
            }

        if pipeline_tables:
            schema_data.setdefault("schemas", {})["pipelines"] = {
                "tables": pipeline_tables,
            }
            schema_data.setdefault("table_names", []).extend(pipeline_tables.keys())
    finally:
        db.close()
    return schema_data


def schema_key_for(connection) -> str:
    """Marker string used as DatabaseConnection.schema_json_path when the
    schema lives in the `schema_json` JSONB column. Format: `db:<conn_id>`.

    Schema data was previously persisted to DO Spaces; we migrated to a DB
    column (see migration sch1ma2jsonb3) after dropping DO. The marker
    preserves the existing API/UI contract that uses truthy
    `schema_json_path` as the "schema exists" flag.
    """
    return f"db:{connection.id}"


def save_schema_file(key: str, schema_json: Dict[str, Any]) -> str:
    """Persist schema JSON to the database. Returns the key marker.

    `key` is expected to be `db:<connection_id>` (from schema_key_for).
    Legacy DO Spaces keys are accepted but logged as deprecated.
    """
    if not key.startswith("db:"):
        logger.warning(
            "save_schema_file: non-DB key %r received -- DO Spaces persistence is removed. "
            "Use schema_key_for() to build a db:<id> marker.", key,
        )
        return key

    conn_id = int(key[3:])
    from backend.database.session import SessionLocal
    from backend.models.database_connection import DatabaseConnection

    _db = SessionLocal()
    try:
        conn = _db.query(DatabaseConnection).filter_by(id=conn_id).first()
        if conn is None:
            raise ValueError(f"No connection with id {conn_id} to save schema for")
        conn.schema_json = schema_json
        conn.schema_json_path = key
        _db.commit()
    finally:
        _db.close()
    logger.info("Schema saved to DB for connection %s", conn_id)
    return key


def load_schema_file(key_or_id) -> Dict[str, Any]:
    """Load schema JSON from the database.

    Accepts either:
      - int: a connection_id (reads schema_json column directly)
      - str "db:<id>": same as above
      - any other str: legacy DO Spaces key -- not supported, raises
    """
    from backend.database.session import SessionLocal
    from backend.models.database_connection import DatabaseConnection

    if isinstance(key_or_id, int):
        conn_id = key_or_id
    elif isinstance(key_or_id, str) and key_or_id.startswith("db:"):
        conn_id = int(key_or_id[3:])
    else:
        raise FileNotFoundError(
            f"Schema not found: legacy DO Spaces key {key_or_id!r} -- "
            "rerun refresh-schema to persist into DB"
        )

    _db = SessionLocal()
    try:
        conn = _db.query(DatabaseConnection).filter_by(id=conn_id).first()
        if not conn or conn.schema_json is None:
            raise FileNotFoundError(f"No schema for connection {conn_id}")
        return conn.schema_json
    finally:
        _db.close()


def delete_schema_file(key: str | None) -> bool:
    """Clear schema_json on the connection identified by key."""
    if not key or not key.startswith("db:"):
        return False
    conn_id = int(key[3:])
    from backend.database.session import SessionLocal
    from backend.models.database_connection import DatabaseConnection

    _db = SessionLocal()
    try:
        conn = _db.query(DatabaseConnection).filter_by(id=conn_id).first()
        if conn is None:
            return False
        conn.schema_json = None
        conn.schema_json_path = None
        _db.commit()
    finally:
        _db.close()
    logger.info("Cleared schema for connection %s", conn_id)
    return True


def refresh_schema(
    key: str,
    connector: BaseConnector,
    connection_id: int,
    connection_name: str,
    db_type: str,
    connection=None,
) -> str:
    """Re-discover and regenerate schema JSON at the given key.

    When *connection* is supplied, the result is augmented with materialised
    pipeline tables (see augment_schema_with_pipelines) so connectors that
    own managed pipelines surface their dedup view + flat columns to the
    dashboard + briefing agents.
    """
    logger.info(f"Refreshing schema at {key}")
    schema_data = discover_schema(connector)
    if connection is not None:
        schema_data = augment_schema_with_pipelines(schema_data, connection)
    schema_json = generate_schema_json(connection_id, connection_name, db_type, schema_data)
    return save_schema_file(key, schema_json)
