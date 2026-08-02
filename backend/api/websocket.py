"""WebSocket endpoint for real-time bidirectional chat and agent notifications."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.database.session import SessionLocal, DetachedReadSessionLocal
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.schemas.chat import ResolvedMention
from backend.services.conversation_service import ConversationService
from backend.services.ws_connection_manager import manager
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def _finalize_credit_turn(credit_mgr, retry_succeeded, orchestrator_errored=False) -> None:
    """Close a turn's credit context: record usage + debit the org pool.

    Called after the answer is persisted and before `done` is forwarded, so the
    client's post-`done` balance refresh reads the debited pool while a persist
    failure still aborts the turn uncharged. Voids first when the turn didn't
    resolve the user's question so they aren't charged for it. No-op when
    credit_mgr is None. The caller nulls credit_mgr after this returns so it is
    invoked exactly once per turn — `__aexit__` is not itself idempotent.

    ``orchestrator_errored`` is the streaming counterpart of the REST path's
    ``success=False``: stream_orchestrator catches its own exceptions and
    reports them as an ``error`` EVENT rather than raising, so nothing here
    sees a failure unless the caller flags it. Same precedence as chat.py — an
    outright failure outranks an unresolved retry.

    The void/charge decision itself lives in `finalize_credit_turn` so the REST
    path (chat.py) applies the identical rules; this wrapper only pins the
    websocket-specific ordering described above.
    """
    from backend.services.token_tracking_service import finalize_credit_turn
    if orchestrator_errored:
        void_reason = "orchestrator reported failure"
    elif retry_succeeded is False:
        void_reason = "layer4_retry_failed"
    else:
        void_reason = None
    await finalize_credit_turn(credit_mgr, void_reason)


async def _complete_turn(
    db,
    conversation,
    is_new: bool,
    user_message: str,
    final_message: str,
    collected_steps: list,
    retry_succeeded,
    judge_metadata,
    credit_mgr,
    pending_done_event,
    send,
    request_id: str,
    user: User,
    active_thread_id: str,
    orchestrator_errored: bool = False,
) -> None:
    """Finish a turn after the orchestrator's `done`, in strict order:
    persist → capture → charge → forward `done` → best-effort post-process.

    Persist runs FIRST; its failure propagates *before* the charge, so a turn
    whose answer wasn't saved is never billed (the caller finalizes the credit
    context with the exception, which skips the charge). `done` is forwarded only
    after the charge lands, so the client's balance refresh reads the debited
    pool. Post-processing failures are swallowed — the turn is already complete.
    """
    # 1. Persist the answer + steps. Must succeed before charging.
    await _persist_turn(db, conversation, final_message, collected_steps)

    # 2. Capture an unresolved Layer-4 retry failure (independent of billing;
    #    the actual void happens inside _finalize_credit_turn).
    if retry_succeeded is False and judge_metadata:
        try:
            from backend.services.agent_failure_capture import capture_failure
            capture_failure(
                db=db,
                user_id=user.id,
                conversation_id=conversation.id,
                thread_id=conversation.thread_id,
                user_question=user_message,
                response_initial=judge_metadata.get("initial_response", ""),
                response_after_retry=judge_metadata.get("retry_response", ""),
                judge_reason_initial=judge_metadata.get("judge_reason_initial", ""),
                judge_reason_retry=judge_metadata.get("judge_reason_retry", ""),
                judge_directive=judge_metadata.get("judge_directive", ""),
                model=settings.default_llm_model or settings.default_llm_provider,
                judge_model=judge_metadata.get("judge_model", ""),
                orchestrator_steps=collected_steps or None,
            )
        except Exception as _capture_err:
            logger.warning("Layer-4 capture failed: %s", _capture_err)

    # 3. Charge now that the answer is safe (voids first if the turn failed or
    #    the retry never resolved), then forward `done`.
    await _finalize_credit_turn(credit_mgr, retry_succeeded, orchestrator_errored)
    if pending_done_event is not None:
        await send(pending_done_event)

    # 4. Best-effort post-processing; a failure here must not undo the charge.
    try:
        await _postprocess_turn(
            db, conversation, is_new, user_message, final_message,
            collected_steps, send, request_id, user, active_thread_id,
        )
    except Exception as _pp_err:
        logger.warning("Post-processing failed after turn completed: %s", _pp_err)


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
        # Pre-created empty shells (e.g. file-upload flow) still deserve title generation
        # on their first real user turn.
        if conversation.type == "task" and ConversationService.count_user_messages(db, conversation.id) == 0:
            is_new = True
    else:
        conversation = ConversationService.create_conversation(db, user.id, title="New Task")

    # Validate connection access (own connections + the shared read-only sample)
    if connection_ids:
        from sqlalchemy import or_
        from backend.services.seed import shared_sample_clause
        accessible = db.query(DatabaseConnection.id).filter(
            DatabaseConnection.id.in_(connection_ids),
            or_(
                DatabaseConnection.user_id == user.id,
                shared_sample_clause(),
            ),
        ).all()
        if len(accessible) != len(connection_ids):
            await send({"type": "chat.error", "request_id": request_id, "thread_id": conversation.thread_id, "content": "Access denied to one or more connections"})
            return None, False

    return conversation, is_new


def _render_dataset_summary(conn, connection_id: int, context: dict) -> str:
    """Render a dataset connection as a routing summary — deliberately not a data dictionary.

    The orchestrator only needs enough to recognise the dataset and hand it to
    data_agent. Column names, types and glossary descriptions are withheld on
    purpose: given them, the model answers "tell me more about this dataset" by
    paraphrasing the schema instead of querying it, since a data dictionary is a
    complete-looking answer to that question and no statistic is present to
    suggest otherwise. The agents that actually write SQL build their own
    full-schema blocks (data_agent.build_dataset_context_block, and the
    dashboard_agent context suffix), so nothing downstream loses information.
    """
    lines = [
        f"=== Dataset: {conn.source_filename or conn.name} ===",
        f"Connection ID: {connection_id} (queryable via SQL)",
    ]
    for table_name, table_info in (context.get("tables") or {}).items():
        # Stored contexts use camelCase; _build_schema_fallback writes snake_case.
        row_count = table_info.get("rowCount", table_info.get("row_count"))
        columns = table_info.get("columns") or {}
        parts = [f"table {table_name}"]
        if row_count is not None:
            parts.append(f"{row_count:,} rows")
        if columns:
            parts.append(f"{len(columns)} columns")
        line = f"- {', '.join(parts)}"
        if table_info.get("description"):
            line += f" — {table_info['description']}"
        lines.append(line)
    lines.append(
        "Schema metadata only — no column list, no data values. To say anything about "
        "what this data contains or shows, query it through data_agent; do not describe "
        "the dataset from this block."
    )
    return "\n".join(lines)


def _build_dataset_file_content(db: Session, user: User, connection_id: int) -> Optional[dict]:
    """Build a synthetic file_contents entry from a DatabaseConnection record.

    Dataset files uploaded via the connections API are not stored in Redis, so
    _resolve_attachments cannot find them with a normal chat_file_service lookup.
    This helper reconstructs the data that build_user_message() needs.
    """
    from sqlalchemy import or_
    from backend.services.seed import shared_sample_clause
    conn = db.query(DatabaseConnection).filter(
        DatabaseConnection.id == connection_id,
        or_(
            DatabaseConnection.user_id == user.id,
            shared_sample_clause(),
        ),
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

    if conn.profiling_status == "ready" and conn.data_context is not None:
        try:
            # Enriched: overlays the semantic layer so the table description written
            # by the dataset docs task travels with the summary.
            from backend.services.semantic_layer import load_enriched_context
            context = load_enriched_context(db, connection_id) or conn.data_context
            profile_text = _render_dataset_summary(conn, connection_id, context)
            file_data["profile_text"] = profile_text
            file_data["truncated_text"] = profile_text
            file_data["profile_status"] = "ready"
        except Exception:
            file_data.update(_build_schema_fallback(conn, connection_id))
    elif conn.profiling_status in ("pending", "in_progress"):
        file_data["profile_status"] = "processing"
        file_data["truncated_text"] = _build_schema_fallback(conn, connection_id)["truncated_text"]
    else:
        file_data.update(_build_schema_fallback(conn, connection_id))

    return file_data


def _build_schema_fallback(conn, connection_id: int) -> dict:
    """Build minimal dataset info from schema JSON when profiling isn't complete.

    Counts only, no column names — same reasoning as _render_dataset_summary.
    """
    lines = [f"=== Dataset: {conn.source_filename or conn.name} ==="]
    lines.append(f"Connection ID: {connection_id} (queryable via SQL)")
    try:
        from backend.services.schema_discovery import load_schema_file
        schema = load_schema_file(connection_id)
        for schema_name, schema_data in schema.get("schemas", {}).items():
            for table_name, table_data in schema_data.get("tables", {}).items():
                columns = table_data.get("columns", [])
                row_count = table_data.get("row_count")
                parts = [f"table {table_name}"]
                if row_count is not None:
                    parts.append(f"{row_count:,} rows")
                if columns:
                    parts.append(f"{len(columns)} columns")
                lines.append(f"- {', '.join(parts)}")
    except (FileNotFoundError, Exception):
        pass
    lines.append(
        "Schema metadata only — no column list, no data values. To say anything about "
        "what this data contains or shows, query it through data_agent; do not describe "
        "the dataset from this block."
    )
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

    # Privacy: under metadata_only_llm, withhold the raw-row preview
    # (truncated_text) that's shown before async profiling completes. The richer
    # profile_text is already gated at generation time (profile_chat_file).
    if file_contents and user is not None and db is not None:
        from backend.services.llm_privacy import metadata_only_for_user
        if metadata_only_for_user(db, getattr(user, "id", None)):
            for f in file_contents:
                if f.get("truncated_text"):
                    f["truncated_text"] = (
                        "[Data preview withheld by org privacy policy; the file is "
                        "being profiled — describe shape from column names/types.]"
                    )

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


def _fold_ask_persist_content(event: dict, final_message: str) -> str:
    """Fold the ask_user_question force-stop's body into the message to persist.

    That force-stop yields `done` with no preceding `token` events, so
    `final_message` is empty and the turn would persist as an empty assistant
    message — which replays as `AIMessage(content="")` on the next turn and is a
    provider-compatibility hazard besides.

    Pops rather than reads, so the key never reaches the client-visible `done`
    payload (which spreads every remaining event key). A turn that actually
    streamed tokens keeps them: this is a fallback, not an override.
    """
    content = event.pop("persist_content", None)
    if content and not final_message:
        return content
    return final_message


async def _persist_turn(
    db: Session,
    conversation,
    final_message: str,
    collected_steps: list,
):
    """Persist the assistant message + steps. Must succeed BEFORE the turn is
    charged — a failure here propagates so credit is never finalized (the caller
    charges only after this returns). Save even for empty/tool-only turns.

    Runs in a worker thread: committing a many-step turn (JSON step payloads
    over TLS to the capped managed PG) blocked the event loop long enough to
    fail liveness probes (2026-07-23 incident)."""
    if final_message or collected_steps:
        await asyncio.to_thread(
            _persist_turn_sync, db, conversation, final_message, collected_steps
        )


def _persist_turn_sync(
    db: Session,
    conversation,
    final_message: str,
    collected_steps: list,
):
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


async def _postprocess_turn(
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
    """Best-effort tail: title/summary generation + completion broadcasts. Runs
    AFTER the answer is persisted, charged, and `done` is forwarded, so a failure
    here neither undoes the charge nor errors an already-completed turn."""
    # Generate title for new conversations. Broadcast via the connection manager so
    # every tab's sidebar refreshes live, not just the tab that sent the message.
    if is_new and (final_message or collected_steps):
        from backend.services.title_service import generate_title, fallback_title
        try:
            title = await generate_title(user_message, final_message or "", steps=collected_steps)
        except Exception:
            logger.exception("Title generation failed; using fallback")
            title = fallback_title(user_message)
        ConversationService.update_title(db, conversation.id, title)
        await manager.send_to_user(user.id, {
            "type": "chat.title",
            "request_id": request_id,
            "thread_id": conversation.thread_id,
            "content": title,
        })

    # Generate/update conversation summary
    if final_message:
        try:
            from backend.services.summary_service import SummaryService
            summary = await SummaryService.generate_or_update_summary(
                db, conversation.id, user_message, final_message
            )
            token_count = SummaryService.estimate_conversation_tokens(db, conversation.id)
            token_limit = SummaryService.get_token_limit()
            await manager.send_to_user(user.id, {
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


async def _wait_for_file_processing(
    file_ids: list,
    db: Session,
    user: User,
    send,
    request_id: str,
    thread_id: str,
) -> bool:
    """Gate: wait until all connection:N file_ids have profiling_status == 'ready'.

    Pushes chat.waiting events while polling, chat.ready when done,
    chat.error on failure/timeout. Returns True if all files are ready,
    False if the turn should abort.
    """
    if not file_ids:
        return True

    MAX_WAIT_S = 300  # 5-minute timeout per file
    POLL_INTERVAL_S = 2

    pending: dict[int, str] = {}  # connection_id → name
    for fid in file_ids:
        if not fid.startswith("connection:"):
            continue
        try:
            cid = int(fid.split(":", 1)[1])
            conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == cid,
                DatabaseConnection.user_id == user.id,
            ).first()
            if conn and conn.profiling_status not in ("ready", "failed"):
                pending[cid] = conn.source_filename or conn.name or f"file #{cid}"
        except (ValueError, Exception):
            continue

    if not pending:
        return True

    for cid, name in pending.items():
        await send({
            "type": "chat.waiting",
            "request_id": request_id,
            "thread_id": thread_id,
            "content": {
                "file_id": f"connection:{cid}",
                "name": name,
                "connection_id": cid,
            },
        })

    elapsed = 0
    while pending:
        # Don't hold the pooled connection across the sleep: profiling can run for
        # minutes, and a connection left idle-in-transaction gets reaped by the
        # pooler. Closing also drops the identity map, so the query below opens a
        # fresh transaction and reads the Celery worker's committed write directly —
        # no refresh() needed.
        db.close()
        await asyncio.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S

        resolved: list[int] = []
        for cid in list(pending.keys()):
            conn = db.query(DatabaseConnection).filter(
                DatabaseConnection.id == cid,
                DatabaseConnection.user_id == user.id,
            ).first()
            if conn is None:
                resolved.append(cid)
                continue
            if conn.profiling_status == "ready":
                resolved.append(cid)
            elif conn.profiling_status == "failed":
                name = pending[cid]
                await send({
                    "type": "chat.error",
                    "request_id": request_id,
                    "thread_id": thread_id,
                    "content": f"Processing failed for {name}",
                })
                return False

        for cid in resolved:
            del pending[cid]

        if elapsed >= MAX_WAIT_S:
            names = ", ".join(pending.values())
            await send({
                "type": "chat.error",
                "request_id": request_id,
                "thread_id": thread_id,
                "content": f"Timed out waiting for {names} to finish processing",
            })
            return False

    await send({
        "type": "chat.ready",
        "request_id": request_id,
        "thread_id": thread_id,
        "content": "All files ready",
    })
    return True


async def _handle_chat_send(
    ws: WebSocket,
    user: User,
    request_id: str,
    thread_id: Optional[str],
    message: str,
    connection_ids: list,
    file_ids: list = None,
    mentions: list = None,
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
    db: Session = DetachedReadSessionLocal()
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
        # Already windowed and cut at the last context reset, in SQL.
        history = ConversationService.get_conversation_history(db, conversation.thread_id, user.id)

        # Wait for any connection:N files still being profiled by Celery
        if not await _wait_for_file_processing(
            file_ids, db, user, send, request_id, active_thread_id,
        ):
            return  # processing failed — error already pushed

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

        # Resolve provider + LLM call settings from the published agent profile
        # (draft edits stay confined to settings until publish).
        from backend.agents.profile_llm import resolve_published_llm
        user_provider, profile_temperature, profile_max_tokens = resolve_published_llm(ctx.profile)

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
                # Phase 4 of multi-user-org: distinguish per-user daily cap
                # exhaustion from org pool exhaustion so the UI can render
                # the right copy.
                cap = getattr(_credit_setup_err, "reason", "user_daily")
                if cap == "org_pool":
                    msg = "Organization credit pool exhausted. Contact your bingo admin."
                else:
                    # Not a daily cap — that was removed. A "user_daily" reason
                    # is now a per-request minimum shortfall from
                    # provider_wrapper, which no midnight reset will fix.
                    msg = "Not enough credits to run this request."
                await send({
                    "type": "chat.error",
                    "request_id": request_id,
                    "thread_id": conversation.thread_id,
                    "content": msg,
                    "error_code": "insufficient_credits",
                    "cap": cap,
                })
                return
            logger.warning("Credit context setup failed: %s", _credit_setup_err)
            _credit_mgr = None

        # Stream orchestrator
        from backend.database.session import SessionLocal as _SF

        # Return the pooled connection before the (minutes-long) stream — held open it
        # sits idle-in-transaction, the pooler reaps it, and the post-stream writes die
        # with "SSL connection has been closed unexpectedly". Rows loaded above
        # (conversation, history, ctx.custom_agents, ctx.user_skills) survive as
        # detached-but-populated objects because this handler's session comes from
        # DetachedReadSessionLocal (expire_on_commit=False)
        # — only their column attrs are safe past this point, never a lazy relationship.
        # The session re-opens lazily (pre-pinged) on the next statement; the orchestrator
        # has its own session factory (_SF) and does not use this one.
        db.close()

        final_message = ""
        collected_steps = []
        collected_retry_succeeded = None
        collected_judge_metadata = None
        pending_done_event = None
        orchestrator_errored = False

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
            mentions=mentions or None,
            temperature=profile_temperature,
            max_tokens=profile_max_tokens,
        ):
            # Map SSE event type → WS event type
            event_type = event.get("type", "")
            ws_type = f"chat.{event_type}" if event_type else "chat.unknown"

            # Buffer the `done` event: capture Layer-4 metadata but do NOT forward
            # it yet. The answer must be persisted and the turn charged first, then
            # `done` is sent — so the client's balance refresh reads the debited
            # pool AND a persist failure can still abort the turn without charging.
            if event_type == "done":
                if "steps" in event:
                    collected_steps = event.get("steps", [])
                collected_retry_succeeded = event.pop("retry_succeeded", None)
                collected_judge_metadata = event.pop("judge_metadata", None)
                final_message = _fold_ask_persist_content(event, final_message)
                pending_done_event = {
                    "type": ws_type,
                    "request_id": request_id,
                    "thread_id": conversation.thread_id,
                    "content": event.get("content") or event.get("status"),
                    **({k: v for k, v in event.items() if k not in ("type", "content", "status")}),
                }
                continue  # `done` is terminal; forward it after persist + charge

            # stream_orchestrator reports its own failures as an `error` event
            # and then stops without a `done` (graph.py) — nothing raises, so
            # this flag is the only signal that the turn produced no answer.
            if event_type == "error":
                orchestrator_errored = True

            await send({
                "type": ws_type,
                "request_id": request_id,
                "thread_id": conversation.thread_id,
                "content": event.get("content") or event.get("status"),
                **({k: v for k, v in event.items() if k not in ("type", "content", "status")}),
            })

            if event_type == "token":
                final_message += event.get("content", "")

        # Complete the turn in order: persist → charge → forward `done` →
        # post-process. Persist failure raises out of here BEFORE the charge, so
        # the handler below finalizes with the exception (no charge). _credit_mgr
        # is nulled only on success so the except/finally don't re-exit it.
        await _complete_turn(
            db, conversation, is_new_conversation, message, final_message,
            collected_steps, collected_retry_succeeded, collected_judge_metadata,
            _credit_mgr, pending_done_event, send, request_id, user, active_thread_id,
            orchestrator_errored,
        )
        _credit_mgr = None

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


# Chat turns are designed to outlive their socket (see the endpoint's finally),
# so they must stay referenced after the endpoint frame is gone. The endpoint's
# own set cannot do that: it is reachable only through the task's done-callback,
# so set and task form a cycle that nothing else holds once the frame dies.
#
# In practice the loop anchors a task that has a wakeup registered with it — a
# timer, a selector callback, an executor callback, or a ready handle — and a
# chat turn awaiting an LLM call or DB work always has one. A task with *no*
# such wakeup is collectable, and the cyclic collector does take it (CPython
# prints "Task was destroyed but it is pending!"). This makes the guarantee
# hold by construction rather than by that coincidence.
_inflight_chat_tasks: set[asyncio.Task] = set()


async def _close_quietly(ws: WebSocket) -> None:
    try:
        await ws.close(code=1011)
    except Exception:
        pass


def _on_listener_done(task: asyncio.Task, ws: WebSocket, user_id: str) -> None:
    """Close the socket if the Redis listener ever stops on its own.

    `listen_redis` resubscribes forever, so finishing at all means it raised out
    of its own retry loop. The socket would then stay open answering pings while
    nothing published over Redis ever reaches it, and the client reconnects only
    on close — so close it and let the frontend's existing backoff take over.
    """
    if task.cancelled():
        return  # normal teardown from the endpoint's finally
    exc = task.exception()
    if exc is None:
        return
    logger.error("WS Redis listener died for user=%s: %r", user_id, exc)
    asyncio.create_task(_close_quietly(ws))


def _log_task_exception(task: asyncio.Task) -> None:
    """Surface anything that escaped a chat.send task's own error handling.

    `_handle_chat_send` catches `Exception` around its whole body, so reaching
    here means the failure happened in that handler or in the `finally` — where
    it was previously swallowed until GC printed "Task exception was never
    retrieved", if at all.
    """
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("chat.send task failed: %r", exc, exc_info=exc)


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
    redis_task.add_done_callback(lambda t: _on_listener_done(t, ws, user.id))

    # The one-turn-per-socket gate. Scoped to this connection on purpose, so it
    # dies with the frame; the strong reference that has to outlive the socket is
    # _inflight_chat_tasks.
    chat_tasks: set[asyncio.Task] = set()

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
                raw_mentions = data.get("mentions") or []
                mentions: list[ResolvedMention] = []
                for raw in raw_mentions:
                    try:
                        mentions.append(ResolvedMention.model_validate(raw))
                    except Exception as exc:
                        logger.warning("Dropping invalid @-mention payload: %r (%s)", raw, exc)

                if not message:
                    await ws.send_text(json.dumps({
                        "type": "chat.error",
                        "request_id": request_id,
                        "thread_id": thread_id or "",
                        "content": "Empty message",
                    }))
                    continue

                if chat_tasks:
                    # The composer is disabled while a turn streams, so a second
                    # send on the same socket is a duplicate or a scripted
                    # client. One turn per socket stops a single authenticated
                    # connection from fanning out N orchestrator runs on the
                    # pod's only event loop.
                    await ws.send_text(json.dumps({
                        "type": "chat.error",
                        "request_id": request_id,
                        "thread_id": thread_id or "",
                        "content": "A message is already being answered on this connection.",
                        "error_code": "busy",
                    }))
                    continue

                # Fire-and-forget so this loop stays responsive
                task = asyncio.create_task(_handle_chat_send(
                    ws, user, request_id, thread_id, message, connection_ids,
                    file_ids=file_ids,
                    mentions=mentions,
                ))
                chat_tasks.add(task)
                _inflight_chat_tasks.add(task)
                task.add_done_callback(chat_tasks.discard)
                task.add_done_callback(_inflight_chat_tasks.discard)
                task.add_done_callback(_log_task_exception)

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
        # chat_tasks are deliberately NOT cancelled. Outliving the socket is the
        # designed behaviour: the run finishes, persists the answer, and
        # publishes chat.stream_complete over Redis, which the reconnected
        # socket picks up (frontend useChatConversations.checkStreamingViaWs
        # sends stream.check and waits for it). Cancelling here would discard a
        # completed, already-charged turn on every wifi blip.
        manager.disconnect(user.id, ws)
