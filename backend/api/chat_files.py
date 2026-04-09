import logging
import posixpath
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.config import settings
from backend.database.session import get_db
from backend.models.user import User
from backend.services import chat_file_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

ACCEPTED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "text/csv",
    "text/xlsx",
    "text/xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("/conversations/create")
async def create_conversation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new conversation for file uploads (before the actual upload)."""
    from backend.services.conversation_service import ConversationService
    conversation = ConversationService.create_conversation(
        db, user_id=current_user.id, title="File Upload"
    )
    return {"thread_id": conversation.thread_id}


@router.post("/files/upload")
async def upload_chat_files(
    files: List[UploadFile] = File(...),
    thread_id: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Upload files for use in a chat session.

    Accepts images (PNG, JPEG, GIF, WEBP), CSV, PDF, and DOCX files.
    Files are processed, stored temporarily in Redis (1-hour TTL), and
    file IDs are returned for reference in subsequent chat requests.

    If thread_id is provided, files are associated with that conversation.
    If thread_id is null, a new conversation is auto-created.
    """
    from backend.services.conversation_service import ConversationService

    if len(files) > settings.chat_file_max_count:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {settings.chat_file_max_count} files allowed per upload.",
        )

    # Resolve or create conversation
    if thread_id:
        conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
        if not conversation:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        conversation = ConversationService.create_conversation(
            db, user_id=current_user.id, title="File Upload"
        )
        thread_id = conversation.thread_id

    results = []

    for upload_file in files:
        file_bytes = await upload_file.read()
        file_size = len(file_bytes)

        # Validate file size
        if file_size > settings.chat_file_max_size:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File '{upload_file.filename}' is too large. "
                    "Files over 10MB are not supported in chat. "
                    "Consider using a database connection instead."
                ),
            )

        # Validate MIME type
        mime_type = upload_file.content_type or ""
        if mime_type not in ACCEPTED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"File '{upload_file.filename}' has unsupported type '{mime_type}'. "
                    f"Accepted types: {', '.join(sorted(ACCEPTED_MIME_TYPES))}."
                ),
            )

        try:
            file_data = chat_file_service.process_file(
                file_bytes=file_bytes,
                filename=upload_file.filename or "",
                mime_type=mime_type,
            )
            file_data["thread_id"] = thread_id
            chat_file_service.store_file(file_data)
            storage_key = chat_file_service.save_raw_file(
                current_user.id, file_data["file_id"], upload_file.filename or "", file_bytes, mime_type
            )
            chat_file_service.update_file_storage_key(file_data["file_id"], storage_key)

            is_dataset = file_data.get("profile_status") == "processing"

            # Kick off async profiling for dataset files (CSV/Excel)
            # Note: CSV/Excel files primarily go through /api/connections/upload-dataset
            # which handles the full pipeline. This path is a fallback for direct API calls.
            if is_dataset:
                from backend.tasks.profiling_tasks import profile_chat_file
                profile_chat_file.delay(file_data["file_id"])
        except ValueError as exc:
            logger.warning("Failed to process chat file '%s': %s", upload_file.filename, exc)
            raise HTTPException(status_code=400, detail=str(exc))

        result = {
            "file_id": file_data["file_id"],
            "name": file_data["original_name"],
            "type": file_data["mime_type"],
            "size": file_data["size"],
            "content_type": file_data["content_type"],
            "thread_id": thread_id,
            "auto_processing": is_dataset,
        }
        results.append(result)

        logger.info(
            "Processed chat file '%s' (type=%s, size=%d) -> file_id=%s, thread_id=%s",
            upload_file.filename,
            mime_type,
            file_size,
            file_data["file_id"],
            thread_id,
        )

    return {"files": results, "thread_id": thread_id}


@router.get("/files/{file_id}/url")
async def get_chat_file_url(
    file_id: str,
    storage_key: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate a presigned download URL for a chat file stored in DO Spaces."""
    from backend.services import object_storage

    # Try Redis cache first
    if not storage_key:
        file_data = chat_file_service.get_file(file_id)
        storage_key = file_data.get("storage_key") if file_data else None

    # Fallback: look up storage_key from DB message attachments
    if not storage_key:
        storage_key = _lookup_storage_key_from_db(file_id, current_user.id)

    if not storage_key:
        raise HTTPException(status_code=404, detail="File not found in storage")

    # Normalize path and reject traversal attempts
    normalized = posixpath.normpath(storage_key)
    if ".." in normalized:
        raise HTTPException(status_code=400, detail="Invalid storage key")

    expected_prefix = f"{settings.do_spaces_base_path}/{current_user.id}/"
    if not normalized.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Access denied")

    url = object_storage.generate_presigned_url(normalized, expires_in=3600)
    return {"url": url, "expires_in": 3600}


@router.delete("/files/{file_id}/dataset")
async def cancel_dataset(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Cancel/delete a processing dataset associated with a chat file upload."""
    from backend.models.database_connection import DatabaseConnection
    from backend.services.ws_connection_manager import ConnectionManager

    # Find the file in Redis to get thread_id and verify ownership
    file_data = chat_file_service.get_file(file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")

    thread_id = file_data.get("thread_id")

    # Find the associated DatabaseConnection
    connection = (
        db.query(DatabaseConnection)
        .filter(
            DatabaseConnection.source_filename == file_data.get("original_name"),
            DatabaseConnection.user_id == current_user.id,
            DatabaseConnection.is_ephemeral.is_(True),
        )
        .order_by(DatabaseConnection.id.desc())
        .first()
    )

    if connection:
        # Revoke any running Celery task
        try:
            from backend.tasks.upload_tasks import celery_app as _celery
            _celery.control.revoke(f"create_dataset_from_upload-{file_id}", terminate=True)
        except Exception:
            pass  # Best-effort revocation

        db.delete(connection)
        db.commit()

    # Clean Redis cache
    chat_file_service.delete_file(file_id)

    # Push WebSocket cancelled event
    if thread_id:
        ConnectionManager.publish_to_user_sync(current_user.id, {
            "type": "dataset.status",
            "file_id": file_id,
            "thread_id": thread_id,
            "step": "cancelled",
        })

    return {"status": "cancelled", "file_id": file_id}


@router.get("/conversations/{thread_id}/datasets")
async def get_conversation_datasets(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get all datasets associated with a conversation thread."""
    from backend.services.conversation_service import ConversationService
    from backend.models.database_connection import DatabaseConnection

    # Validate thread ownership
    conversation = ConversationService.get_conversation_by_thread(db, thread_id, current_user.id)
    if not conversation:
        raise HTTPException(status_code=403, detail="Access denied")

    # Find all file_ids in Redis that belong to this thread
    datasets = []
    import redis as _redis
    r = _redis.from_url(settings.redis_url, decode_responses=True)
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor, match=f"{chat_file_service.CHAT_FILE_PREFIX}*", count=100)
        for key in keys:
            raw = r.get(key)
            if not raw:
                continue
            import json
            fd = json.loads(raw)
            if fd.get("thread_id") != thread_id:
                continue
            if fd.get("profile_status") != "processing":
                continue

            # Find associated connection
            conn = (
                db.query(DatabaseConnection)
                .filter(
                    DatabaseConnection.source_filename == fd.get("original_name"),
                    DatabaseConnection.user_id == current_user.id,
                    DatabaseConnection.is_ephemeral.is_(True),
                )
                .order_by(DatabaseConnection.id.desc())
                .first()
            )

            dataset_info = {
                "file_id": fd["file_id"],
                "name": fd.get("original_name", ""),
                "status": conn.profiling_status if conn else "processing",
                "connection_id": conn.id if conn else None,
            }
            datasets.append(dataset_info)

        if cursor == 0:
            break

    r.close()
    return {"datasets": datasets, "thread_id": thread_id}


def _lookup_storage_key_from_db(file_id: str, user_id: str) -> Optional[str]:
    """Look up a file's storage_key from message attachments in the database."""
    from backend.database.session import SessionLocal
    from backend.models.message import Message
    from backend.models.conversation import Conversation
    from sqlalchemy import cast, String

    db = SessionLocal()
    try:
        messages = (
            db.query(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .filter(
                Conversation.user_id == user_id,
                Message.attachments.isnot(None),
            )
            .all()
        )
        for msg in messages:
            if not msg.attachments:
                continue
            for att in msg.attachments:
                if att.get("file_id") == file_id and att.get("storage_key"):
                    return att["storage_key"]
        return None
    finally:
        db.close()
