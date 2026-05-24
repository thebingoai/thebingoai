"""Celery tasks for connection profiling and data context generation."""

import logging
from datetime import datetime, timezone

from celery import shared_task
from backend.database.session import SessionLocal

logger = logging.getLogger(__name__)


@shared_task(name="profile_connection", bind=True, max_retries=2, time_limit=600)
def profile_connection(self, connection_id: int):
    """Profile all tables for a connection and build a data context.

    This task:
    1. Loads the already-discovered schema for the connection.
    2. Profiles each table (stats per column).
    3. Infers column roles (dimension/measure/key/attribute) and relationships.
    4. Saves the resulting data context to disk.
    5. Updates the connection's profiling_status to ``ready``.

    On failure, sets status to ``failed`` and retries up to ``max_retries``
    times with exponential back-off.
    """
    from backend.models.database_connection import DatabaseConnection, ProfilingStatus
    from backend.connectors.factory import get_connector_for_connection, get_connector_registration
    from backend.services.schema_discovery import load_schema_file
    from backend.services.table_profiler import profile_table
    from backend.services.connection_context import build_connection_context, save_connection_context

    db = SessionLocal()
    try:
        connection = db.query(DatabaseConnection).filter(
            DatabaseConnection.id == connection_id,
        ).first()
        if not connection:
            logger.warning("profile_connection: connection %d not found", connection_id)
            return

        # Mark in-progress
        connection.profiling_status = ProfilingStatus.IN_PROGRESS.value
        connection.profiling_error = None
        connection.profiling_started_at = datetime.now(timezone.utc)
        db.commit()

        # Load the schema that was already discovered at connection creation
        try:
            schema_json = load_schema_file(connection_id)
        except FileNotFoundError:
            connection.profiling_status = ProfilingStatus.FAILED.value
            connection.profiling_error = "Schema file not found. Please refresh the connection schema first."
            db.commit()
            return

        # Determine connector metadata
        reg = get_connector_registration(connection.db_type)
        if reg and reg.skip_profiling:
            connection.profiling_status = ProfilingStatus.READY.value
            connection.profiling_progress = "skipped"
            db.commit()
            logger.info("profile_connection %d: skipped (connector opted out)", connection_id)
            return
        is_dataset = reg is not None and reg.type_id == "dataset"
        if connection.db_type == "bigquery":
            db_type_str = "bigquery"
        elif connection.db_type == "mysql":
            db_type_str = "mysql"
        else:
            db_type_str = "postgres"

        # Collect all tables from all schemas
        tables_to_profile: list[tuple[str, str, dict]] = []  # (schema_name, table_name, table_data)
        for schema_name, schema_data in schema_json.get("schemas", {}).items():
            for table_name, table_data in schema_data.get("tables", {}).items():
                tables_to_profile.append((schema_name, table_name, table_data))

        total = len(tables_to_profile)
        logger.info("profile_connection %d: profiling %d table(s)", connection_id, total)

        # Profile each table
        table_profiles: dict[str, dict] = {}

        connector = get_connector_for_connection(connection)
        try:
            for idx, (schema_name, table_name, table_data) in enumerate(tables_to_profile, 1):
                # Update progress
                connection.profiling_progress = f"{idx}/{total} tables"
                db.commit()

                try:
                    result = profile_table(
                        connector=connector,
                        table_name=table_name,
                        schema_name=schema_name,
                        columns=table_data.get("columns", []),
                        row_count=table_data.get("row_count", 0),
                        db_type=db_type_str,
                        is_dataset=is_dataset,
                    )
                    table_profiles[table_name] = result
                except Exception as table_err:
                    logger.warning(
                        "profile_connection %d: failed to profile table %s: %s",
                        connection_id, table_name, table_err,
                    )
                    table_profiles[table_name] = {"table_name": table_name, "columns": {}, "error": str(table_err)}
        finally:
            connector.close()

        # For connectors with managed pipelines (e.g. bigquery_ga4 -> bronze
        # + dedup view), also profile the materialised target table via the
        # data plane. Without this, the dashboard agent sees the table in
        # schema_json (added by augment_schema_with_pipelines) but with no
        # profile -> no dimension/measure roles -> dashboard build refuses.
        if connection.db_type == "bigquery_ga4":
            try:
                from backend.data_plane.scope import OwnerScope
                from backend.models.pipeline import Pipeline
                from backend.services.data_plane_service import get_default_plane

                pipelines = db.query(Pipeline).filter(
                    Pipeline.source_connection_id == connection_id,
                ).all()
                for p in pipelines:
                    try:
                        scope = OwnerScope(kind=p.owner_scope_kind, id=p.owner_scope_id)
                        plane = get_default_plane(scope, db)
                        prof = _profile_table(scope, plane, p.target_table, "pipeline")
                        if prof:
                            table_profiles[p.target_table] = prof
                            logger.info(
                                "profile_connection %d: profiled managed pipeline table %s",
                                connection_id, p.target_table,
                            )
                    except Exception:
                        logger.exception(
                            "profile_connection %d: pipeline table %s profile failed",
                            connection_id, p.target_table,
                        )
            except Exception:
                logger.exception(
                    "profile_connection %d: managed-pipeline profile block failed",
                    connection_id,
                )

        # Build context from schema + profiles
        context = build_connection_context(connection_id, schema_json, table_profiles)

        # Persist to database_connections.data_context (JSONB)
        save_connection_context(db, connection_id, context)

        # Mark ready
        connection.profiling_status = ProfilingStatus.READY.value
        connection.profiling_progress = f"{total}/{total} tables"
        connection.profiling_completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info("profile_connection %d: completed — %d tables profiled", connection_id, total)

    except Exception as e:
        logger.error("profile_connection %d failed: %s", connection_id, e)
        try:
            connection = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == connection_id,
            ).first()
            if connection:
                connection.profiling_status = ProfilingStatus.FAILED.value
                connection.profiling_error = str(e)
                db.commit()
        except Exception:
            db.rollback()

        # Retry with exponential back-off (60s, 120s)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()


@shared_task(name="profile_chat_file", time_limit=120)
def profile_chat_file(file_id: str):
    """Profile an uploaded CSV/Excel chat file in the background.

    Reads the raw file bytes back from the Redis-cached file data,
    runs the dataset profiler, and updates the Redis entry with
    the profile_text and profile_status='ready'.
    """
    import io
    import json

    import pandas as pd
    import redis

    from backend.config import settings
    from backend.profiler.dataset_profiler import profile_dataframe
    from backend.services.chat_file_service import CHAT_FILE_PREFIX

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    key = f"{CHAT_FILE_PREFIX}{file_id}"
    raw = redis_client.get(key)
    if raw is None:
        logger.warning("profile_chat_file: file %s not found in Redis (expired?)", file_id)
        return

    file_data = json.loads(raw)
    mime_type = file_data.get("mime_type", "")

    # Re-read the raw file from object storage
    from backend.services import object_storage

    storage_key = file_data.get("storage_key")
    if not storage_key:
        logger.warning("profile_chat_file: no storage_key for file %s", file_id)
        file_data["profile_status"] = "ready"
        ttl = max(redis_client.ttl(key), 60)
        redis_client.setex(key, ttl, json.dumps(file_data))
        return

    file_bytes = object_storage.download_bytes(storage_key)
    if file_bytes is None:
        logger.warning("profile_chat_file: could not download %s", storage_key)
        file_data["profile_status"] = "ready"
        ttl = max(redis_client.ttl(key), 60)
        redis_client.setex(key, ttl, json.dumps(file_data))
        return

    try:
        if "csv" in mime_type:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
            except Exception:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
        else:
            df = pd.read_excel(io.BytesIO(file_bytes))

        profile = profile_dataframe(df)
        profile_text = profile.to_prompt_text("")

        file_data["profile_text"] = profile_text
        file_data["profile_status"] = "ready"
        file_data["metadata"]["profiled"] = True
    except Exception as exc:
        logger.warning("profile_chat_file: profiling failed for %s: %s", file_id, exc)
        file_data["profile_status"] = "ready"  # Mark ready so chat isn't blocked forever

    ttl = max(redis_client.ttl(key), 60)
    redis_client.setex(key, ttl, json.dumps(file_data))
    logger.info("profile_chat_file: completed for file %s", file_id)


def _arrow_type_canonical(arrow_type) -> str:
    """Map a pyarrow DataType to a canonical SQL-style type name so
    downstream consumers (connection_context.infer_column_role,
    NUMERIC_TYPES / DATE_TYPES sets in table_profiler) match correctly.

    Without this, types like `date32[day]` or `timestamp[us, tz=UTC]` fall
    through `infer_column_role` and every column ends up as `attribute`,
    which the dashboard agent treats as non-dimension.
    """
    try:
        import pyarrow as pa
    except Exception:
        return str(arrow_type)
    t = arrow_type
    if pa.types.is_date(t):
        return "date"
    if pa.types.is_timestamp(t):
        return "timestamp"
    if pa.types.is_time(t):
        return "time"
    if pa.types.is_floating(t):
        return "float64"
    if pa.types.is_integer(t):
        return "int64"
    if pa.types.is_boolean(t):
        return "boolean"
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return "string"
    return str(t)


def _profile_table(scope, plane, table_name: str, source_type: str) -> dict:
    """Read column types from DataPlane for *table_name* and return a profile dict."""
    try:
        schema = plane.get_schema(scope, table_name)
        columns = {
            field.name: {
                "type": _arrow_type_canonical(field.type),
                "nullable": field.nullable,
            }
            for field in schema
        }
        return {"columns": columns, "source_type": source_type, "table_name": table_name}
    except Exception as exc:
        logger.warning("_profile_table: failed for %s/%s: %s", source_type, table_name, exc)
        return {}


@shared_task(name="profile_pipeline_output", bind=True, max_retries=1, time_limit=300)
def profile_pipeline_output(self, pipeline_id: str, run_id: str):
    """Profile the output table of a pipeline run and emit profile.diff if columns changed."""
    from backend.database.session import SessionLocal
    from backend.models.pipeline import Pipeline
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane
    from backend.notifications import publish

    db = SessionLocal()
    try:
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        if not pipeline:
            logger.warning("profile_pipeline_output: pipeline %s not found", pipeline_id)
            return

        scope = OwnerScope(pipeline.owner_scope_kind, pipeline.owner_scope_id)
        plane = get_default_plane(scope, db)

        # Read previous profile (stored on pipeline row as last_profile_columns JSONB)
        prev_columns = getattr(pipeline, "last_profile_columns", None) or {}

        # Get current profile
        new_profile = _profile_table(scope, plane, pipeline.target_table, "pipeline")
        new_columns = new_profile.get("columns", {})

        if new_columns:
            # Compute diff
            added = [{"name": k, "type": v["type"]} for k, v in new_columns.items() if k not in prev_columns]
            removed = [{"name": k, "type": v["type"]} for k, v in prev_columns.items() if k not in new_columns]
            type_changes = [
                {"name": k, "old_type": prev_columns[k]["type"], "new_type": v["type"]}
                for k, v in new_columns.items()
                if k in prev_columns and prev_columns[k]["type"] != v["type"]
            ]

            if added or removed or type_changes:
                publish({
                    "event_type": "profile.diff",
                    "scope": {"kind": pipeline.owner_scope_kind, "id": pipeline.owner_scope_id},
                    "resource_type": "pipeline",
                    "resource_id": pipeline_id,
                    "table_name": pipeline.target_table,
                    "added_columns": added,
                    "removed_columns": removed,
                    "type_changes": type_changes,
                    "run_id": run_id,
                    "run_finished_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("profile.diff published for pipeline %s: +%d -%d ~%d cols",
                            pipeline_id, len(added), len(removed), len(type_changes))

            # Update stored profile on the pipeline row
            # Note: Pipeline model doesn't have last_profile_columns yet — use column_count as proxy
            pipeline.column_count = len(new_columns) if hasattr(pipeline, "column_count") else None

        db.commit()
        logger.info("profile_pipeline_output done for pipeline %s run %s", pipeline_id, run_id)

        # For pipeline-only connectors (skip_profiling=True), the connection's
        # profiling_status stays 'pending' after OAuth connect so the UI shows yellow.
        # Update it to 'ready' now that the pipeline has run successfully, and
        # persist a minimal data_context so the dashboard agent has something to read.
        try:
            from backend.models.database_connection import DatabaseConnection, ProfilingStatus
            conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == pipeline.source_connection_id
            ).first()
            if conn and conn.profiling_status == ProfilingStatus.PENDING.value:
                conn.profiling_status = ProfilingStatus.READY.value

                # Build minimal context from the saved schema. `build_connection_context`
                # accepts an empty table_profiles dict and still emits tables + relationships
                # — enough for the dashboard agent's build_dashboard_context to validate
                # table and dimension names. Per-cell stats remain absent for pipeline flows.
                try:
                    from backend.services.schema_discovery import load_schema_file
                    from backend.services.connection_context import (
                        build_connection_context,
                        save_connection_context,
                    )
                    schema_json = load_schema_file(conn.id)
                    context = build_connection_context(conn.id, schema_json, {})
                    save_connection_context(db, conn.id, context)
                    conn.profiling_completed_at = datetime.now(timezone.utc)
                except Exception as ctx_err:
                    logger.warning(
                        "profile_pipeline_output: failed to build minimal context for connection %d: %s",
                        conn.id, ctx_err,
                    )

                db.commit()
                logger.info("profile_pipeline_output: updated connection %d profiling_status to ready", conn.id)
        except Exception as e:
            logger.warning("profile_pipeline_output: failed to update connection profiling_status: %s", e)
            db.rollback()

    except Exception as exc:
        logger.error("profile_pipeline_output failed for pipeline %s: %s", pipeline_id, exc)
        # Profile failure does NOT fail the run — just log
    finally:
        db.close()


@shared_task(name="profile_dbt_model", bind=True, max_retries=1, time_limit=300)
def profile_dbt_model(self, run_id: str, model_name: str, scope_kind: str, scope_id: str):
    """Profile the output table of a dbt model run and emit profile.diff if columns changed.

    Mirrors profile_pipeline_output but for dbt models.
    """
    from backend.database.session import SessionLocal
    from backend.models.transforms import DbtModel, DbtRun
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane
    from backend.notifications import publish

    db = SessionLocal()
    try:
        # Find the DbtModel by name+scope
        model = db.query(DbtModel).filter(
            DbtModel.owner_scope_kind == scope_kind,
            DbtModel.owner_scope_id == scope_id,
            DbtModel.name == model_name,
        ).first()
        if not model:
            logger.warning("profile_dbt_model: model %s not found in scope %s/%s", model_name, scope_kind, scope_id)
            return

        scope = OwnerScope(scope_kind, scope_id)
        plane = get_default_plane(scope, db)

        # Read previous profile (stored on model row — add last_profile_columns attribute if missing)
        prev_columns = getattr(model, "last_profile_columns", None) or {}

        # Get current profile
        new_profile = _profile_table(scope, plane, model_name, "dbt_model")
        new_columns = new_profile.get("columns", {})

        if new_columns:
            added = [{"name": k, "type": v["type"]} for k, v in new_columns.items() if k not in prev_columns]
            removed = [{"name": k, "type": v["type"]} for k, v in prev_columns.items() if k not in new_columns]
            type_changes = [
                {"name": k, "old_type": prev_columns[k]["type"], "new_type": v["type"]}
                for k, v in new_columns.items()
                if k in prev_columns and prev_columns[k]["type"] != v["type"]
            ]

            if added or removed or type_changes:
                publish({
                    "event_type": "profile.diff",
                    "scope": {"kind": scope_kind, "id": scope_id},
                    "resource_type": "dbt_model",
                    "resource_id": str(model.id),
                    "table_name": model_name,
                    "added_columns": added,
                    "removed_columns": removed,
                    "type_changes": type_changes,
                    "run_id": run_id,
                    "run_finished_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("profile.diff published for dbt model %s: +%d -%d ~%d cols",
                            model_name, len(added), len(removed), len(type_changes))

            # Persist the profile so future runs can diff against it
            model.last_profile_columns = new_columns

        db.commit()
        logger.info("profile_dbt_model done for model %s run %s", model_name, run_id)

    except Exception as exc:
        logger.error("profile_dbt_model failed for model %s: %s", model_name, exc)
    finally:
        db.close()


@shared_task(name="backfill_profile_all_connections")
def backfill_profile_all_connections():
    """One-time task: queue profiling for all existing connections that have
    a schema but no data context yet.

    Called on app startup to migrate existing connections after the feature is
    deployed.
    """
    from backend.models.database_connection import DatabaseConnection, ProfilingStatus

    db = SessionLocal()
    try:
        pending = (
            db.query(DatabaseConnection)
            .filter(
                DatabaseConnection.profiling_status == ProfilingStatus.PENDING.value,
                DatabaseConnection.schema_json_path.isnot(None),
            )
            .all()
        )

        if not pending:
            logger.info("backfill_profile_all_connections: no pending connections")
            return

        logger.info("backfill_profile_all_connections: queuing %d connection(s)", len(pending))
        for conn in pending:
            profile_connection.delay(conn.id)

    except Exception as e:
        logger.error("backfill_profile_all_connections failed: %s", e)
    finally:
        db.close()
