"""WebSocket endpoint for real-time bidirectional chat and agent notifications."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.database.session import SessionLocal
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.services.conversation_service import ConversationService
from backend.services.ws_connection_manager import manager
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def _get_user_from_token(token: str) -> Optional[User]:
    """Validate auth token and return User, or None on failure."""
    from backend.auth.sso import validate_token

    sso_user = await validate_token(token)
    if sso_user is None or not sso_user.is_active or not sso_user.is_verified:
        return None

    from backend.auth.dependencies import _create_user
    from fastapi import HTTPException

    db = SessionLocal()
    try:
        # Look up by sso_id first, then email
        user = db.query(User).filter(User.sso_id == sso_user.id).first()
        if user is None:
            user = db.query(User).filter(User.email == sso_user.email).first()
            if user is not None:
                # Link existing user to SSO
                user.sso_id = sso_user.id
                user.auth_provider = "sso"
                db.commit()
                db.refresh(user)
            else:
                try:
                    # Auto-create new user (same as REST API path)
                    user = _create_user(db, sso_user)
                except HTTPException:
                    return None
        return user
    finally:
        db.close()


async def _resolve_conversation(
    db: Session,
    user: User,
    thread_id: Optional[str],
    connection_ids: list,
    send,
    request_id: str,
):
    """Get or create conversation, validate connection access.
    Returns (conversation, is_new). Raises on error (sends error to client first)."""
    is_new = not thread_id

    if thread_id:
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, user.id)
        if not conversation:
            await send({"type": "chat.error", "request_id": request_id, "thread_id": thread_id or "", "content": "Conversation not found"})
            return None, False
    else:
        conversation = ConversationService.create_conversation(db, user.id, title="New Task")

    # Validate connection access
    if connection_ids:
        accessible = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.id.in_(connection_ids),
            DatabaseConnection.user_id == user.id,
        ).all()
        if len(accessible) != len(connection_ids):
            await send({"type": "chat.error", "request_id": request_id, "thread_id": conversation.thread_id, "content": "Access denied to one or more connections"})
            return None, False

    return conversation, is_new


def _build_dataset_file_content(db: Session, user: User, connection_id: int) -> Optional[dict]:
    """Build a synthetic file_contents entry from a DatabaseConnection record.

    Dataset files uploaded via the connections API are not stored in Redis, so
    _resolve_attachments cannot find them with a normal chat_file_service lookup.
    This helper reconstructs the data that build_user_message() needs.
    """
    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        DatabaseConnection.user_id == user.id,
    ).first()
    if conn is None:
        logger.warning("_build_dataset_file_content: connection %d not found for user %s", connection_id, user.id)
        return None

    file_data: dict = {
        "file_id": f"connection:{connection_id}",
        "original_name": conn.source_filename or conn.name,
        "mime_type": "text/csv",
        "size": 0,
        "content_type": "text",
    }

    if conn.profiling_status == "ready" and conn.data_context_path:
        try:
            from backend.services.connection_context import load_context_file
            context = load_context_file(connection_id)
            profile_lines = [f"=== Dataset Profile: {conn.source_filename or conn.name} ==="]
            profile_lines.append(f"Connection ID: {connection_id} (queryable via SQL)")
            tables = context.get("tables", {})
            for table_name, table_info in tables.items():
                profile_lines.append(f"\nTable: {table_name}")
                row_count = table_info.get("row_count")
                if row_count is not None:
                    profile_lines.append(f"Row count: {row_count:,}")
                columns = table_info.get("columns", {})
                if columns:
                    profile_lines.append("Columns:")
                    for col_name, col_info in list(columns.items())[:50]:
                        col_type = col_info.get("type", "")
                        role = col_info.get("role", "")
                        profile_lines.append(f"  - {col_name} ({col_type}, {role})")
            profile_text = "\n".join(profile_lines)
            file_data["profile_text"] = profile_text
            file_data["truncated_text"] = profile_text
            file_data["profile_status"] = "ready"
        except (FileNotFoundError, Exception):
            file_data.update(_build_schema_fallback(conn, connection_id))
    elif conn.profiling_status in ("pending", "in_progress"):
        file_data["profile_status"] = "processing"
        file_data["truncated_text"] = _build_schema_fallback(conn, connection_id)["truncated_text"]
    else:
        file_data.update(_build_schema_fallback(conn, connection_id))

    return file_data


def _build_schema_fallback(conn, connection_id: int) -> dict:
    """Build minimal dataset info from schema JSON when profiling isn't complete."""
    lines = [f"=== Dataset: {conn.source_filename or conn.name} ==="]
    lines.append(f"Connection ID: {connection_id} (queryable via SQL)")
    try:
        from backend.services.schema_discovery import load_schema_file
        schema = load_schema_file(connection_id)
        for schema_name, schema_data in schema.get("schemas", {}).items():
            for table_name, table_data in schema_data.get("tables", {}).items():
                columns = table_data.get("columns", [])
                row_count = table_data.get("row_count")
                lines.append(f"\nTable: {table_name}")
                if row_count is not None:
                    lines.append(f"Row count: {row_count:,}")
                if columns:
                    col_names = [c.get("name", "") for c in columns]
                    lines.append(f"Columns: {', '.join(col_names)}")
    except (FileNotFoundError, Exception):
        pass
    return {"truncated_text": "\n".join(lines), "profile_status": "ready"}


async def _inject_conversation_datasets(
    db: Session, user: User, thread_id: str,
    agent_context, file_contents: list, chat_file_service,
) -> None:
    """
    Discover ephemeral datasets (uploaded via chat) and inject ready ones
    into the orchestrator context.
    """
    from backend.models.database_connection import DatabaseConnection
    from backend.agents.context import ConnectionInfo

    ephemeral_connections = (
        db.query(DatabaseConnection)
        .filter(
            DatabaseConnection.user_id == user.id,
            DatabaseConnection.is_ephemeral.is_(True),
            DatabaseConnection.is_active.is_(True),
        )
        .all()
    )

    for conn in ephemeral_connections:
        if conn.id not in agent_context.available_connections:
            agent_context.available_connections.append(conn.id)
            agent_context.connection_metadata.append(
                ConnectionInfo(id=conn.id, name=conn.name, db_type=conn.db_type, database=conn.database)
            )


async def _resolve_attachments(file_ids, chat_file_service, db: Session = None, user: User = None):
    """Resolve file_ids to file contents and attachment metadata.

    Handles two file ID formats:
    - Regular UUIDs (e.g. "abc-123"): looked up in Redis via chat_file_service
    - Connection references (e.g. "connection:42"): looked up in PostgreSQL as DatabaseConnection

    Returns (file_contents, attachments).
    """
    file_contents = []
    if file_ids:
        for fid in file_ids:
            if fid.startswith("connection:") and db is not None and user is not None:
                try:
                    connection_id = int(fid.split(":", 1)[1])
                    file_data = _build_dataset_file_content(db, user, connection_id)
                    if file_data is not None:
                        file_contents.append(file_data)
                except (ValueError, Exception) as exc:
                    logger.warning("_resolve_attachments: failed to resolve %s: %s", fid, exc)
            else:
                file_data = chat_file_service.get_file(fid)
                if file_data is not None:
                    file_contents.append(file_data)

    attachments = [
        {
            "file_id": f["file_id"],
            "name": f["original_name"],
            "type": f["mime_type"],
            "size": f["size"],
            "content_type": f["content_type"],
            "storage_key": f.get("storage_key"),
        }
        for f in (file_contents or [])
    ]
    return file_contents, attachments


async def _fire_chat_response_plugins(user_id, thread_id, user_message, assistant_message):
    """Fire plugin on_chat_response hooks. Runs as a background task."""
    try:
        from backend.plugins.loader import fire_chat_response_hooks
        await fire_chat_response_hooks(
            user_id=str(user_id), thread_id=thread_id,
            user_message=user_message, assistant_message=assistant_message,
        )
    except Exception as exc:
        logger.warning("fire_chat_response_plugins error: %s", exc)


async def _persist_and_postprocess(
    db: Session,
    conversation,
    is_new: bool,
    user_message: str,
    final_message: str,
    collected_steps: list,
    send,
    request_id: str,
    user: User,
    active_thread_id: str,
):
    """Persist assistant message, steps, generate title/summary, broadcast completion."""
    # Persist assistant message (save even if empty — tool-only turns
    # like ask_user_question still need steps persisted)
    if final_message or collected_steps:
        assistant_msg = ConversationService.add_message(db, conversation.id, "assistant", final_message or "")

        if collected_steps:
            from backend.models.agent_step import AgentStep
            for i, step in enumerate(collected_steps):
                db.add(AgentStep(
                    message_id=assistant_msg.id,
                    step_number=i + 1,
                    agent_type=step.get("agent_type", "unknown"),
                    step_type=step.get("step_type", "unknown"),
                    tool_name=step.get("tool_name"),
                    content=step.get("content", {}),
                    duration_ms=step.get("duration_ms"),
                ))
            db.commit()

    # Generate title for new conversations
    if is_new and final_message:
        try:
            from backend.services.title_service import generate_title
            title = await generate_title(user_message, final_message, steps=collected_steps)
            ConversationService.update_title(db, conversation.id, title)
            await send({
                "type": "chat.title",
                "request_id": request_id,
                "thread_id": conversation.thread_id,
                "content": title,
            })
        except Exception as title_err:
            logger.warning(f"Title generation failed: {title_err}")

    # Generate/update conversation summary
    if final_message:
        try:
            from backend.services.summary_service import SummaryService
            summary = await SummaryService.generate_or_update_summary(
                db, conversation.id, user_message, final_message
            )
            token_count = SummaryService.estimate_conversation_tokens(db, conversation.id)
            token_limit = SummaryService.get_token_limit()
            await send({
                "type": "chat.summary",
                "request_id": request_id,
                "thread_id": conversation.thread_id,
                "content": {
                    "text": summary.summary_text,
                    "updated_at": summary.updated_at.isoformat(),
                    "token_count": token_count,
                    "token_limit": token_limit,
                }
            })
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")

    # Notify all connected tabs that streaming finished (reaches reconnected WS)
    await manager.send_to_user(user.id, {
        "type": "chat.stream_complete",
        "thread_id": active_thread_id,
    })

    # Fire plugin hooks (non-blocking)
    if final_message:
        asyncio.create_task(_fire_chat_response_plugins(
            user.id, conversation.thread_id, user_message, final_message,
        ))


async def _handle_chat_send(
    ws: WebSocket,
    user: User,
    request_id: str,
    thread_id: Optional[str],
    message: str,
    connection_ids: list,
    file_ids: list = None,
) -> None:
    """
    Handle a chat.send message over WebSocket.
    Mirrors the SSE streaming logic but sends JSON events over the WebSocket.
    """
    from backend.agents import stream_orchestrator
    from backend.services.heartbeat_context import build_orchestrator_context
    from backend.services import chat_file_service

    import redis as sync_redis
    redis_client = sync_redis.from_url(settings.redis_url, decode_responses=True)
    db: Session = SessionLocal()
    active_thread_id: Optional[str] = thread_id  # tracks actual thread_id for cleanup

    async def send(payload: dict) -> None:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            pass

    _credit_mgr = None
    try:
        # Resolve conversation and validate connections
        conversation, is_new_conversation = await _resolve_conversation(
            db, user, thread_id, connection_ids, send, request_id,
        )
        if conversation is None:
            return
        active_thread_id = conversation.thread_id

        # Build orchestrator context
        ctx = await build_orchestrator_context(
            db=db,
            user=user,
            query=message,
            connection_ids=connection_ids or None,
            thread_id=conversation.thread_id,
        )

        # Conversation history (fetched before saving the current user message)
        history = ConversationService.get_conversation_history(db, conversation.thread_id, user.id)
        # Truncate at last context reset boundary
        for i in range(len(history) - 1, -1, -1):
            if history[i].source == "context_reset":
                history = history[i + 1:]
                break

        # Resolve attachments
        file_contents, attachments = await _resolve_attachments(file_ids, chat_file_service, db=db, user=user)

        # Discover conversation datasets (auto-created from uploads)
        await _inject_conversation_datasets(
            db, user, conversation.thread_id,
            ctx.agent_context, file_contents, chat_file_service,
        )

        # Save user message with attachment metadata
        ConversationService.add_message(
            db, conversation.id, "user", message,
            attachments=attachments if attachments else None,
        )

        # Resolve LLM provider from environment config
        from backend.llm.factory import get_provider
        user_provider = get_provider(settings.default_llm_provider)

        # Set Redis streaming flag (TTL 5 min safety net)
        streaming_key = f"streaming:{conversation.thread_id}"
        redis_client.setex(streaming_key, 300, request_id)

        # --- Credit context setup (bingo-credits plugin) ---
        _credit_mgr = None
        _InsufficientCreditsError = None
        try:
            from backend.plugins.loader import get_loaded_plugins
            if "bingo-admin" in get_loaded_plugins():
                from bingo_admin.credit_context import CreditContextManager, InsufficientCreditsError as _InsufficientCreditsError
            else:
                from backend.services.token_tracking_service import CreditContextManager, InsufficientCreditsError as _InsufficientCreditsError
            _credit_mgr = CreditContextManager(
                db=db,
                user_id=user.id,
                title=message[:80],
                provider_name=settings.default_llm_provider,
                conversation_id=conversation.id,
                block_on_insufficient=True,
            )
            await _credit_mgr.__aenter__()
        except Exception as _credit_setup_err:
            if _InsufficientCreditsError and isinstance(_credit_setup_err, _InsufficientCreditsError):
                await send({"type": "chat.error", "request_id": request_id, "thread_id": conversation.thread_id, "content": "Daily credits used up. Resets at midnight.", "error_code": "insufficient_credits"})
                return
            logger.warning("Credit context setup failed: %s", _credit_setup_err)
            _credit_mgr = None

        # Stream orchestrator
        from backend.database.session import SessionLocal as _SF
        final_message = ""
        collected_steps = []
        collected_retry_succeeded = None
        collected_judge_metadata = None

        async for event in stream_orchestrator(
            message,
            ctx.agent_context,
            history=history,
            custom_agents=ctx.custom_agents or None,
            db_session_factory=_SF,
            memory_context=ctx.memory_context,
            user_skills=ctx.user_skills or None,
            user_memories_context=ctx.user_memories_context,
            skill_suggestions=ctx.skill_suggestions or None,
            soul_prompt=ctx.soul_prompt,
            file_contents=file_contents or None,
            profile=ctx.profile,
            llm_provider=user_provider,
        ):
            # Map SSE event type → WS event type
            event_type = event.get("type", "")
            ws_type = f"chat.{event_type}" if event_type else "chat.unknown"

            # Capture Layer-4 metadata from done event before forwarding
            if event_type == "done":
                if "steps" in event:
                    collected_steps = event.get("steps", [])
                collected_retry_succeeded = event.pop("retry_succeeded", None)
                collected_judge_metadata = event.pop("judge_metadata", None)

            await send({
                "type": ws_type,
                "request_id": request_id,
                "thread_id": conversation.thread_id,
                "content": event.get("content") or event.get("status"),
                **({k: v for k, v in event.items() if k not in ("type", "content", "status")}),
            })

            if event_type == "token":
                final_message += event.get("content", "")

        # Persist message, steps, generate title/summary, broadcast completion
        await _persist_and_postprocess(
            db, conversation, is_new_conversation, message, final_message,
            collected_steps, send, request_id, user, active_thread_id,
        )

        # Layer 5: void credit + capture failure case if Layer-4 retry still failed
        if collected_retry_succeeded is False:
            if _credit_mgr is not None and hasattr(_credit_mgr, "void"):
                try:
                    _credit_mgr.void("layer4_retry_failed")
                except Exception as _void_err:
                    logger.warning("Credit void failed: %s", _void_err)
            if collected_judge_metadata:
                try:
                    from backend.services.agent_failure_capture import capture_failure
                    capture_failure(
                        db=db,
                        user_id=user.id,
                        conversation_id=conversation.id,
                        thread_id=conversation.thread_id,
                        user_question=message,
                        response_initial=collected_judge_metadata.get("initial_response", ""),
                        response_after_retry=collected_judge_metadata.get("retry_response", ""),
                        judge_reason_initial=collected_judge_metadata.get("judge_reason_initial", ""),
                        judge_reason_retry=collected_judge_metadata.get("judge_reason_retry", ""),
                        judge_directive=collected_judge_metadata.get("judge_directive", ""),
                        model=settings.default_llm_model or settings.default_llm_provider,
                        judge_model=collected_judge_metadata.get("judge_model", ""),
                        orchestrator_steps=collected_steps or None,
                    )
                except Exception as _capture_err:
                    logger.warning("Layer-4 capture failed: %s", _capture_err)

        # --- Finalize credit usage (bingo-credits plugin) ---
        if _credit_mgr is not None:
            try:
                await _credit_mgr.__aexit__(None, None, None)
            except Exception as _credit_err:
                logger.warning("Credit usage recording failed: %s", _credit_err)

    except Exception as e:
        if _credit_mgr is not None:
            try:
                await _credit_mgr.__aexit__(type(e), e, e.__traceback__)
            except Exception:
                pass
        logger.exception(f"chat.send error: {e}")
        await send({"type": "chat.error", "request_id": request_id, "thread_id": thread_id or "", "content": str(e)})
    finally:
        # Clear streaming flag (may not exist if error occurred before streaming started)
        if active_thread_id:
            try:
                redis_client.delete(f"streaming:{active_thread_id}")
            except Exception:
                pass
        db.close()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket endpoint.

    Auth: pass JWT as ?token=<JWT> query param.

    Client → Server messages:
        {"type": "ping"}
        {"type": "chat.send", "request_id": "uuid", "thread_id": "uuid|null", "message": "...", "connection_ids": []}
        {"type": "conversation.switch"}  (no-op — frontend state only)

    Server → Client messages: see ws protocol spec in plan.
    """
    token = ws.query_params.get("token")
    if not token:
        await ws.accept()
        await ws.close(code=4001, reason="Missing token")
        return

    user = await _get_user_from_token(token)
    if not user:
        await ws.accept()
        await ws.close(code=4003, reason="Unauthorized")
        return

    await ws.accept()
    manager.connect(user.id, ws)

    # Start Redis listener as background task
    redis_task = asyncio.create_task(manager.listen_redis(user.id, ws))

    try:
        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect:
                break

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"type": "error", "content": "Invalid JSON"}))
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "chat.send":
                request_id = data.get("request_id", "")
                thread_id = data.get("thread_id") or None
                message = data.get("message", "").strip()
                connection_ids = data.get("connection_ids", [])
                file_ids = data.get("file_ids", [])

                if not message:
                    await ws.send_text(json.dumps({
                        "type": "chat.error",
                        "request_id": request_id,
                        "thread_id": thread_id or "",
                        "content": "Empty message",
                    }))
                    continue

                # Fire-and-forget so this loop stays responsive
                asyncio.create_task(_handle_chat_send(
                    ws, user, request_id, thread_id, message, connection_ids,
                    file_ids=file_ids,
                ))

            elif msg_type == "conversation.switch":
                pass  # Frontend-only state change

            elif msg_type == "stream.check":
                check_thread_id = data.get("thread_id") or None
                if check_thread_id:
                    import redis as _sr
                    _rc = _sr.from_url(settings.redis_url, decode_responses=True)
                    try:
                        is_streaming = _rc.exists(f"streaming:{check_thread_id}") > 0
                    finally:
                        _rc.close()
                    await ws.send_text(json.dumps({
                        "type": "stream.status",
                        "thread_id": check_thread_id,
                        "streaming": is_streaming,
                    }))

            elif msg_type == "context.reset":
                reset_thread_id = data.get("thread_id") or None
                if reset_thread_id:
                    db_reset: Session = SessionLocal()
                    try:
                        conv_reset = ConversationService.get_conversation_by_thread(db_reset, reset_thread_id, user.id)
                        if conv_reset:
                            msg_reset = ConversationService.add_context_reset(db_reset, conv_reset.id)
                            await ws.send_text(json.dumps({
                                "type": "context.reset_ack",
                                "thread_id": reset_thread_id,
                                "message_id": msg_reset.id,
                                "timestamp": msg_reset.timestamp.isoformat(),
                            }))
                    except Exception as reset_err:
                        logger.exception(f"context.reset error: {reset_err}")
                    finally:
                        db_reset.close()

            else:
                logger.debug(f"Unknown WS message type: {msg_type}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"WS error for user {user.id}: {e}")
    finally:
        redis_task.cancel()
        manager.disconnect(user.id, ws)
