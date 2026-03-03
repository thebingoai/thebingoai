"""WebSocket endpoint for real-time bidirectional chat and agent notifications."""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend.auth.jwt import decode_access_token
from backend.auth.token_revocation import is_token_revoked
from backend.database.session import SessionLocal
from backend.models.user import User
from backend.models.database_connection import DatabaseConnection
from backend.services.conversation_service import ConversationService
from backend.services.ws_connection_manager import manager
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

_TITLE_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}


async def _generate_title(user_message: str, assistant_response: str) -> str:
    from backend.llm.factory import get_provider
    provider_name = settings.default_llm_provider or "openai"
    model = _TITLE_MODELS.get(provider_name)
    provider = get_provider(provider_name, model=model)
    messages = [
        {
            "role": "user",
            "content": (
                f"User: {user_message}\n\n"
                f"Assistant: {assistant_response[:500]}\n\n"
                "Generate a concise title (3-8 words) for this conversation. "
                "Return ONLY the title text."
            ),
        }
    ]
    raw = await provider.chat(messages, temperature=0.3, max_tokens=30)
    title = raw.strip().strip('"\'').rstrip(".,!?;:")[:80]
    return title or "Untitled"


def _get_user_from_token(token: str) -> Optional[User]:
    """Validate JWT and return User, or None on failure."""
    if is_token_revoked(token):
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


async def _handle_chat_send(
    ws: WebSocket,
    user: User,
    request_id: str,
    thread_id: Optional[str],
    message: str,
    connection_ids: list,
) -> None:
    """
    Handle a chat.send message over WebSocket.
    Mirrors the SSE streaming logic but sends JSON events over the WebSocket.
    """
    from backend.agents import stream_orchestrator
    from backend.services.heartbeat_context import build_orchestrator_context

    db: Session = SessionLocal()

    async def send(payload: dict) -> None:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            pass

    try:
        is_new_conversation = not thread_id

        # Get or create conversation
        if thread_id:
            conversation = ConversationService.get_conversation_by_thread(db, thread_id, user.id)
            if not conversation:
                await send({"type": "chat.error", "request_id": request_id, "thread_id": thread_id or "", "content": "Conversation not found"})
                return
        else:
            conversation = ConversationService.create_conversation(db, user.id, title="New Task")

        # Save user message
        ConversationService.add_message(db, conversation.id, "user", message)

        # Validate connection access
        if connection_ids:
            accessible = db.query(DatabaseConnection.id).filter(
                DatabaseConnection.id.in_(connection_ids),
                DatabaseConnection.user_id == user.id,
            ).all()
            if len(accessible) != len(connection_ids):
                await send({"type": "chat.error", "request_id": request_id, "thread_id": conversation.thread_id, "content": "Access denied to one or more connections"})
                return

        # Build orchestrator context
        ctx = await build_orchestrator_context(
            db=db,
            user=user,
            query=message,
            connection_ids=connection_ids or None,
            thread_id=conversation.thread_id,
        )

        # Conversation history (exclude just-saved user message)
        history = ConversationService.get_conversation_history(db, conversation.thread_id, user.id)
        history = history[:-1]

        # Stream orchestrator
        from backend.database.session import SessionLocal as _SF
        final_message = ""
        collected_steps = []

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
        ):
            # Map SSE event type → WS event type
            event_type = event.get("type", "")
            ws_type = f"chat.{event_type}" if event_type else "chat.unknown"

            await send({
                "type": ws_type,
                "request_id": request_id,
                "thread_id": conversation.thread_id,
                "content": event.get("content") or event.get("status"),
                **({k: v for k, v in event.items() if k not in ("type", "content", "status")}),
            })

            if event_type == "token":
                final_message += event.get("content", "")
            if event_type == "done" and "steps" in event:
                collected_steps = event.get("steps", [])

        # Persist assistant message
        if final_message:
            assistant_msg = ConversationService.add_message(db, conversation.id, "assistant", final_message)

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
        if is_new_conversation and final_message:
            try:
                title = await _generate_title(message, final_message)
                ConversationService.update_title(db, conversation.id, title)
                await send({
                    "type": "chat.title",
                    "request_id": request_id,
                    "thread_id": conversation.thread_id,
                    "content": title,
                })
            except Exception as title_err:
                logger.warning(f"Title generation failed: {title_err}")

    except Exception as e:
        logger.exception(f"chat.send error: {e}")
        await send({"type": "chat.error", "request_id": request_id, "thread_id": thread_id or "", "content": str(e)})
    finally:
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
        await ws.close(code=4001, reason="Missing token")
        return

    user = _get_user_from_token(token)
    if not user:
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
                    ws, user, request_id, thread_id, message, connection_ids
                ))

            elif msg_type == "conversation.switch":
                pass  # Frontend-only state change

            else:
                logger.debug(f"Unknown WS message type: {msg_type}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception(f"WS error for user {user.id}: {e}")
    finally:
        redis_task.cancel()
        manager.disconnect(user.id, ws)
