"""Celery tasks for async file processing."""

from celery import Celery
from datetime import datetime
from typing import Optional

from backend.config import settings
from backend.parser.markdown import chunk_markdown, count_tokens
from backend.embedder.openai import embed_batch_sync
from backend.vectordb.pinecone import upsert_vectors_sync
from backend.services.job_store import (
    start_job, update_progress, complete_job, fail_job
)
import logging

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "llm_md_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_url
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
)


@celery_app.task(bind=True, max_retries=3)
def process_upload_async(
    self,
    job_id: str,
    file_content: str,
    file_name: str,
    namespace: str,
    tags: list[str],
    webhook_url: Optional[str] = None
):
    """
    Process file upload asynchronously.

    Args:
        job_id: Unique job identifier
        file_content: File content as string
        file_name: Original file name
        namespace: Pinecone namespace
        tags: List of tags
        webhook_url: Optional webhook to notify on completion
    """
    logger.info(f"Starting async upload job {job_id} for {file_name}")

    try:
        # 1. Parse and chunk
        logger.info(f"Chunking {file_name}...")
        chunks = chunk_markdown(
            file_content,
            settings.chunk_size,
            settings.chunk_overlap
        )

        if not chunks:
            raise ValueError("No content to index in file")

        total_chunks = len(chunks)
        logger.info(f"Created {total_chunks} chunks")

        # Mark job as started
        start_job(job_id, chunks_total=total_chunks)

        # 2. Embed in batches
        logger.info(f"Embedding {total_chunks} chunks...")
        chunk_texts = [c["text"] for c in chunks]

        # Update progress
        update_progress(job_id, chunks_processed=0, progress=10)

        embeddings = embed_batch_sync(chunk_texts)

        update_progress(job_id, chunks_processed=total_chunks, progress=50)

        # 3. Prepare vectors
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors.append({
                "id": f"{file_name}#chunk-{i}",
                "values": embedding,
                "metadata": {
                    "source": file_name,
                    "chunk_index": i,
                    "text": chunk["text"],
                    "tags": tags,
                    "created_at": datetime.utcnow().isoformat()
                }
            })

        update_progress(job_id, chunks_processed=total_chunks, progress=75)

        # 4. Upsert to Pinecone
        logger.info(f"Upserting {len(vectors)} vectors to Pinecone...")
        result = upsert_vectors_sync(vectors, namespace)
        upserted_count = result.get("upserted_count", len(vectors))

        logger.info(f"Upserted {upserted_count} vectors")

        # 5. Mark complete
        complete_job(
            job_id=job_id,
            file_name=file_name,
            chunks_created=total_chunks,
            vectors_upserted=upserted_count,
            namespace=namespace
        )

        # 6. Send webhook if configured
        if webhook_url:
            _send_webhook(webhook_url, {
                "job_id": job_id,
                "status": "completed",
                "file_name": file_name,
                "namespace": namespace,
                "chunks_created": total_chunks,
                "vectors_upserted": upserted_count
            })

        logger.info(f"Job {job_id} completed successfully")
        return {
            "job_id": job_id,
            "status": "completed",
            "file_name": file_name,
            "chunks_created": total_chunks,
            "vectors_upserted": upserted_count
        }

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")

        # Mark job as failed
        fail_job(job_id, str(e))

        # Send failure webhook
        if webhook_url:
            _send_webhook(webhook_url, {
                "job_id": job_id,
                "status": "failed",
                "file_name": file_name,
                "error": str(e)
            })

        # Retry with exponential backoff
        try:
            self.retry(countdown=60 * (2 ** self.request.retries), exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            raise


def _send_webhook(url: str, payload: dict):
    """Send webhook notification."""
    import httpx
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        response.raise_for_status()
        logger.info(f"Webhook sent to {url}")
    except Exception as e:
        logger.error(f"Failed to send webhook: {e}")
