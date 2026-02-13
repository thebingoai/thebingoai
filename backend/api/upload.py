import uuid
from datetime import datetime
from fastapi import UploadFile, File, Form, HTTPException, Depends
from typing import Optional
from backend.config import settings
from backend.auth.dependencies import get_current_user
from backend.models.user import User
from backend.parser.markdown import chunk_markdown, count_tokens
from backend.embedder.openai import embed_batch
from backend.vectordb.pinecone import upsert_vectors
from backend.services.job_store import create_job
from backend.tasks.upload_tasks import process_upload_async
from backend.models.responses import UploadResponse
from backend.utils.vector_utils import prepare_vectors
import logging

logger = logging.getLogger(__name__)

async def upload_file(
    file: UploadFile = File(...),
    namespace: str = Form("default"),
    tags: str = Form(""),
    webhook_url: Optional[str] = Form(None),
    force_async: str = Form("false"),
    current_user: User = Depends(get_current_user)
) -> UploadResponse:
    """
    Upload and index a markdown file.

    Small files process synchronously, large files are queued.
    """
    # Validate file
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(400, "Only .md files are supported")

    content = await file.read()
    file_size = len(content)

    # Check file size limit
    if file_size > settings.upload_max_file_size:
        max_mb = settings.upload_max_file_size / (1024 * 1024)
        raise HTTPException(413, f"File too large. Maximum size is {max_mb:.0f}MB")

    try:
        content_str = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be valid UTF-8 text")
    tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    should_async = force_async.lower() == "true"

    # Determine if async processing needed
    if not should_async:
        if file_size > settings.async_file_size_threshold:
            should_async = True
        else:
            estimated_tokens = count_tokens(content_str)
            estimated_chunks = estimated_tokens // int(settings.chunk_size * 0.8)
            if estimated_chunks > settings.async_chunk_count_threshold:
                should_async = True

    if should_async:
        # Queue for async processing
        job_id = str(uuid.uuid4())
        create_job(job_id, file.filename, namespace)

        process_upload_async.delay(
            job_id=job_id,
            file_content=content_str,
            file_name=file.filename,
            namespace=namespace,
            tags=tags_list,
            webhook_url=webhook_url
        )

        return UploadResponse(
            status="queued",
            file_name=file.filename,
            namespace=namespace,
            job_id=job_id,
            message="File queued for processing",
            webhook_url=webhook_url
        )

    # Sync processing
    logger.info(f"Processing {file.filename} synchronously")

    # 1. Chunk
    chunks = chunk_markdown(content_str, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise HTTPException(400, "No content to index in file")

    # 2. Embed
    chunk_texts = [c["text"] for c in chunks]
    embeddings = await embed_batch(chunk_texts)

    # 3. Prepare vectors
    vectors = prepare_vectors(file.filename, chunks, embeddings, tags_list)

    # 4. Upsert
    result = await upsert_vectors(vectors, namespace)

    return UploadResponse(
        status="success",
        file_name=file.filename,
        chunks_created=len(chunks),
        vectors_upserted=result.get("upserted_count", len(chunks)),
        namespace=namespace
    )
