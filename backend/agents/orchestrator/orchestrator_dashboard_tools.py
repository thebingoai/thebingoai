import uuid
from datetime import datetime

from langchain_core.tools import tool
from backend.agents.context import AgentContext
from backend.agents.dashboard_agent import invoke_dashboard_agent
from typing import List, Optional, Callable
import json
import logging

logger = logging.getLogger(__name__)


def build_dashboard_tools(context: AgentContext, db_session_factory: Optional[Callable] = None) -> List:
    """Return dashboard tools when db_session_factory is available."""
    if db_session_factory is None:
        return []

    @tool
    async def create_dashboard(request: str) -> str:
        """
        Create a persistent, fully-featured dashboard from a natural language request.

        IMPORTANT: If the user wants a dashboard from an uploaded file, you MUST call
        create_dataset_from_upload FIRST and wait for its result (which contains the
        connection_id), THEN call this tool. Do NOT call both tools simultaneously.

        This tool delegates to a specialized dashboard sub-agent that handles the entire
        dashboard creation workflow autonomously, end-to-end:

        1. **Schema exploration**: Connects to the user's database(s) and discovers available
           tables, columns, data types, and relationships — no prior knowledge of the schema
           is required.

        2. **SQL generation**: Designs and validates SQL queries tailored to the user's request,
           adapting to the actual structure of the data found during schema exploration.

        3. **Widget creation**: Produces a variety of visual widget types based on what best
           suits the underlying data:
              - KPI cards (single-value metrics, e.g. total revenue, active users)
              - Bar charts (comparisons across categories)
              - Line charts (trends over time)
              - Tables (detailed row-level data or multi-column summaries)

        4. **Dashboard assembly**: Arranges widgets into a coherent layout and persists the
           dashboard so the user can view and interact with it immediately.

        Use this tool whenever the user asks to create, build, or make a dashboard — even if
        they have not specified exact metrics, charts, or data sources. The sub-agent will
        autonomously determine what data is available and what visualisations are appropriate.
        There is no need to ask the user for detailed requirements upfront.

        Args:
            request: Natural language description of the dashboard to create. Can be as
                     high-level as "create a sales dashboard" or as specific as "build a
                     dashboard showing monthly revenue by region and top 10 customers".

        Returns:
            JSON string with the following fields:
                - success (bool): Whether the dashboard was created successfully
                - dashboard_id (str): Unique identifier of the created dashboard
                - message (str): Human-readable summary of what was created
                - steps (list): Ordered list of actions taken by the sub-agent
        """
        # Refresh context.available_connections from DB so that any connections created
        # by create_dataset_from_upload in the same turn are visible to the dashboard agent.
        from backend.models.database_connection import DatabaseConnection
        db = db_session_factory()
        try:
            fresh_ids = [
                row.id for row in db.query(DatabaseConnection.id)
                .filter(DatabaseConnection.user_id == context.user_id)
                .all()
            ]
        finally:
            db.close()
        context.available_connections = fresh_ids

        result = await invoke_dashboard_agent(request, context, db_session_factory)
        return json.dumps(result)

    @tool
    async def create_dataset_from_upload(file_id: str) -> str:
        """
        Create a permanent queryable dataset from a CSV or Excel file uploaded in chat.

        Call this BEFORE create_dashboard when the user wants a dashboard from an uploaded
        file. This persists the file as a PostgreSQL table and registers it as a database
        connection that the dashboard agent can query.

        Args:
            file_id: The file_id from the uploaded file (shown in the message as file_id: xxx)

        Returns:
            JSON with connection_id, table_name, column info, row_count, or error message
        """
        from backend.services import chat_file_service
        from backend.services.dataset_service import (
            parse_csv,
            parse_excel,
            sanitize_name,
            infer_column_types,
            create_dataset_sqlite,
            generate_dataset_schema,
        )
        from backend.models.database_connection import DatabaseConnection, DatabaseType
        from backend.models.team_membership import TeamMembership
        from backend.models.team_connection_policy import TeamConnectionPolicy
        from backend.services.schema_discovery import save_schema_file
        from backend.config import settings

        # Find raw file in DO Spaces
        raw_result = chat_file_service.get_raw_file(context.user_id, file_id)
        if not raw_result:
            return json.dumps({"success": False, "message": "File not found or expired. Please re-upload the file."})

        file_bytes, ext = raw_result

        # Get filename from Redis metadata or fall back to file_id + ext
        file_data = chat_file_service.get_file(file_id)
        filename = file_data["original_name"] if file_data else f"dataset{ext}"

        try:
            if ext == ".csv":
                df = parse_csv(file_bytes)
            else:
                df = parse_excel(file_bytes)
        except Exception as e:
            return json.dumps({"success": False, "message": f"Could not parse file: {e}"})

        if len(df) > settings.dataset_max_rows:
            return json.dumps({"success": False, "message": f"File exceeds {settings.dataset_max_rows:,} row limit"})

        if df.empty or len(df.columns) == 0:
            return json.dumps({"success": False, "message": "File is empty or has no columns"})

        columns = infer_column_types(df)
        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        name = base_name.strip() or "dataset"
        sanitized = sanitize_name(base_name)

        db = db_session_factory()
        try:
            connection = DatabaseConnection(
                user_id=context.user_id,
                name=name,
                db_type=DatabaseType.DATASET,
                host="internal",
                port=0,
                database="dataset",
                username="dataset",
                source_filename=filename,
            )
            connection.password = "dataset"
            connection.ssl_ca_cert = None
            db.add(connection)
            db.commit()
            db.refresh(connection)

            from backend.services import object_storage as _object_storage
            from backend.config import settings as _settings

            sqlite_path = create_dataset_sqlite(connection.id, sanitized, columns, df)
            do_spaces_key = f"{_settings.do_spaces_base_path}/datasets/sqlite/{connection.id}.sqlite"
            with open(sqlite_path, 'rb') as f:
                _object_storage.upload_bytes(do_spaces_key, f.read(), content_type="application/x-sqlite3")

            connection.dataset_table_name = do_spaces_key
            db.commit()

            row_count = len(df)
            schema_json = generate_dataset_schema(
                connection_id=connection.id,
                name=name,
                table_name=do_spaces_key,
                columns=columns,
                row_count=row_count,
            )
            schema_path = save_schema_file(connection.id, schema_json)
            connection.schema_json_path = schema_path
            connection.schema_generated_at = datetime.utcnow()
            connection.table_count = 1
            db.commit()

            # Auto-enable for creator's teams
            if settings.enable_governance:
                user_memberships = (
                    db.query(TeamMembership)
                    .filter(TeamMembership.user_id == context.user_id)
                    .all()
                )
                for membership in user_memberships:
                    db.add(TeamConnectionPolicy(
                        id=str(uuid.uuid4()),
                        team_id=membership.team_id,
                        connection_id=connection.id,
                    ))
                if user_memberships:
                    db.commit()

            # Make the new connection immediately available for dashboard creation
            context.available_connections.append(connection.id)

            logger.info(
                "Created dataset connection %s from chat upload file_id=%s, key=%s, rows=%d",
                connection.id, file_id, do_spaces_key, row_count,
            )

            return json.dumps({
                "success": True,
                "connection_id": connection.id,
                "table_name": do_spaces_key,
                "columns": [{"name": c["name"], "type": c["pg_type"]} for c in columns],
                "row_count": row_count,
            })
        except Exception as e:
            db.delete(connection)
            db.commit()
            logger.error("create_dataset_from_upload failed for file_id=%s: %s", file_id, e, exc_info=True)
            return json.dumps({"success": False, "message": str(e)})
        finally:
            db.close()

    return [create_dashboard, create_dataset_from_upload]
