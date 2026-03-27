import logging
import posixpath
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from backend.auth.dependencies import get_current_user
from backend.config import settings
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


@router.post("/files/upload")
async def upload_chat_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Upload files for use in a chat session.

    Accepts images (PNG, JPEG, GIF, WEBP), CSV, PDF, and DOCX files.
    Files are processed, stored temporarily in Redis (1-hour TTL), and
    file IDs are returned for reference in subsequent chat requests.
    """
    if len(files) > settings.chat_file_max_count:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {settings.chat_file_max_count} files allowed per upload.",
        )

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
            chat_file_service.store_file(file_data)
            storage_key = chat_file_service.save_raw_file(
                current_user.id, file_data["file_id"], upload_file.filename or "", file_bytes, mime_type
            )
            chat_file_service.update_file_storage_key(file_data["file_id"], storage_key)
        except ValueError as exc:
            logger.warning("Failed to process chat file '%s': %s", upload_file.filename, exc)
            raise HTTPException(status_code=400, detail=str(exc))

        results.append(
            {
                "file_id": file_data["file_id"],
                "name": file_data["original_name"],
                "type": file_data["mime_type"],
                "size": file_data["size"],
                "content_type": file_data["content_type"],
            }
        )

        logger.info(
            "Processed chat file '%s' (type=%s, size=%d) -> file_id=%s",
            upload_file.filename,
            mime_type,
            file_size,
            file_data["file_id"],
        )

    return {"files": results}


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
