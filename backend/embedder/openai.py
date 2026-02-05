import asyncio
from typing import Optional
from openai import AsyncOpenAI, RateLimitError, APIError
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None

def get_client() -> AsyncOpenAI:
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client

async def embed_text(
    text: str,
    model: str = None,
    max_retries: int = 3,
    base_delay: float = 1.0
) -> list[float]:
    """
    Embed a single text string with retry logic.

    Args:
        text: Text to embed
        model: Embedding model (defaults to settings)
        max_retries: Maximum retry attempts
        base_delay: Base delay for exponential backoff

    Returns:
        List of floats (embedding vector)
    """
    client = get_client()
    model = model or settings.embedding_model

    for attempt in range(max_retries):
        try:
            response = await client.embeddings.create(
                input=text,
                model=model
            )
            return response.data[0].embedding

        except RateLimitError as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Rate limited, retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            else:
                raise

        except APIError as e:
            if attempt < max_retries - 1 and e.status_code >= 500:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API error {e.status_code}, retrying in {delay}s")
                await asyncio.sleep(delay)
            else:
                raise

async def embed_batch(
    texts: list[str],
    model: str = None,
    batch_size: int = 100,
    max_retries: int = 3
) -> list[list[float]]:
    """
    Embed multiple texts in batches.

    Args:
        texts: List of texts to embed
        model: Embedding model
        batch_size: Texts per API call (max 2048 for OpenAI)
        max_retries: Retry attempts per batch

    Returns:
        List of embedding vectors
    """
    client = get_client()
    model = model or settings.embedding_model
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]

        for attempt in range(max_retries):
            try:
                response = await client.embeddings.create(
                    input=batch,
                    model=model
                )
                # Sort by index to maintain order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [d.embedding for d in sorted_data]
                all_embeddings.extend(batch_embeddings)
                break

            except RateLimitError as e:
                if attempt < max_retries - 1:
                    delay = 1.0 * (2 ** attempt)
                    logger.warning(f"Rate limited on batch {i//batch_size}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise

            except APIError as e:
                if attempt < max_retries - 1 and e.status_code >= 500:
                    delay = 1.0 * (2 ** attempt)
                    logger.warning(f"API error on batch {i//batch_size}, retrying")
                    await asyncio.sleep(delay)
                else:
                    raise

    return all_embeddings


# Sync wrappers for Celery tasks
def embed_text_sync(text: str, model: str = None) -> list[float]:
    """Synchronous wrapper for embed_text."""
    return asyncio.run(embed_text(text, model))

def embed_batch_sync(texts: list[str], model: str = None, batch_size: int = 100) -> list[list[float]]:
    """Synchronous wrapper for embed_batch."""
    return asyncio.run(embed_batch(texts, model, batch_size))
