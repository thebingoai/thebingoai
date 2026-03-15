import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

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
