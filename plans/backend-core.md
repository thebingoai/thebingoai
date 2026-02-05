# Backend Core Modules

Complete implementations for backend core components: Markdown parser, OpenAI embedder, Pinecone integration, and configuration.

---

## 1. Markdown Chunker

### Create `backend/parser/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/parser/markdown.py`

```python
import tiktoken
import re
from typing import Optional

# Initialize tokenizer
_tokenizer: Optional[tiktoken.Encoding] = None

def get_tokenizer() -> tiktoken.Encoding:
    """Get or create tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.encoding_for_model("gpt-4")
    return _tokenizer

def count_tokens(text: str) -> int:
    """Count tokens in text."""
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))

def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Simple sentence splitter - handles common cases
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_markdown(
    text: str,
    chunk_size: int = 512,
    overlap: float = 0.2
) -> list[dict]:
    """
    Split markdown into overlapping chunks.

    Args:
        text: Raw markdown text
        chunk_size: Target tokens per chunk
        overlap: Overlap ratio (0.0 to 0.5)

    Returns:
        List of chunk dicts with index, text, token_count, char_start, char_end
    """
    if not text.strip():
        return []

    tokenizer = get_tokenizer()
    overlap_tokens = int(chunk_size * overlap)

    # Split by double newlines (paragraphs) first
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk_texts = []
    current_chunk_tokens = 0
    char_position = 0

    def finalize_chunk():
        """Create a chunk from accumulated texts."""
        nonlocal current_chunk_texts, current_chunk_tokens, char_position

        if not current_chunk_texts:
            return

        chunk_text = "\n\n".join(current_chunk_texts)
        chunk_start = text.find(current_chunk_texts[0], char_position)
        if chunk_start == -1:
            chunk_start = char_position
        chunk_end = chunk_start + len(chunk_text)

        chunks.append({
            "index": len(chunks),
            "text": chunk_text,
            "token_count": current_chunk_tokens,
            "char_start": chunk_start,
            "char_end": chunk_end
        })

        # Calculate overlap - keep last N tokens worth of text
        if overlap_tokens > 0 and current_chunk_texts:
            overlap_texts = []
            overlap_count = 0
            for t in reversed(current_chunk_texts):
                t_tokens = count_tokens(t)
                if overlap_count + t_tokens <= overlap_tokens:
                    overlap_texts.insert(0, t)
                    overlap_count += t_tokens
                else:
                    break
            current_chunk_texts = overlap_texts
            current_chunk_tokens = overlap_count
        else:
            current_chunk_texts = []
            current_chunk_tokens = 0

        char_position = chunk_end

    for para in paragraphs:
        para_tokens = count_tokens(para)

        # If single paragraph exceeds chunk_size, split by sentences
        if para_tokens > chunk_size:
            # Finalize current chunk first
            if current_chunk_texts:
                finalize_chunk()

            sentences = split_into_sentences(para)
            for sent in sentences:
                sent_tokens = count_tokens(sent)

                # If single sentence exceeds chunk_size, force split by tokens
                if sent_tokens > chunk_size:
                    tokens = tokenizer.encode(sent)
                    for i in range(0, len(tokens), chunk_size - overlap_tokens):
                        chunk_tokens = tokens[i:i + chunk_size]
                        chunk_text = tokenizer.decode(chunk_tokens)
                        chunk_start = text.find(chunk_text[:50], char_position)
                        if chunk_start == -1:
                            chunk_start = char_position

                        chunks.append({
                            "index": len(chunks),
                            "text": chunk_text,
                            "token_count": len(chunk_tokens),
                            "char_start": chunk_start,
                            "char_end": chunk_start + len(chunk_text)
                        })
                        char_position = chunk_start + len(chunk_text)
                else:
                    if current_chunk_tokens + sent_tokens > chunk_size:
                        finalize_chunk()
                    current_chunk_texts.append(sent)
                    current_chunk_tokens += sent_tokens
        else:
            # Normal paragraph - check if it fits
            if current_chunk_tokens + para_tokens > chunk_size:
                finalize_chunk()
            current_chunk_texts.append(para)
            current_chunk_tokens += para_tokens

    # Don't forget the last chunk
    if current_chunk_texts:
        finalize_chunk()

    return chunks


def extract_metadata(text: str) -> dict:
    """Extract YAML frontmatter if present."""
    metadata = {}

    # Check for YAML frontmatter
    if text.startswith("---"):
        end_match = re.search(r'\n---\s*\n', text[3:])
        if end_match:
            yaml_content = text[3:end_match.start() + 3]
            try:
                import yaml
                metadata = yaml.safe_load(yaml_content) or {}
            except Exception:
                pass

    return metadata
```

---

## 2. OpenAI Embedder with Retry

### Create `backend/embedder/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/embedder/openai.py`

```python
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
```

---

## 3. Pinecone Integration

### Create `backend/vectordb/__init__.py`

```python
# Empty file - package marker
```

### Create `backend/vectordb/pinecone.py`

```python
from pinecone import Pinecone, ServerlessSpec
from typing import Optional
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

_pc: Optional[Pinecone] = None
_index = None

def init_pinecone() -> None:
    """Initialize Pinecone client and ensure index exists."""
    global _pc, _index

    _pc = Pinecone(api_key=settings.pinecone_api_key)

    # Check if index exists
    existing_indexes = [idx.name for idx in _pc.list_indexes()]

    if settings.pinecone_index_name not in existing_indexes:
        logger.info(f"Creating Pinecone index: {settings.pinecone_index_name}")
        _pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region=settings.pinecone_environment
            )
        )

    _index = _pc.Index(settings.pinecone_index_name)
    logger.info(f"Connected to Pinecone index: {settings.pinecone_index_name}")

def get_index():
    """Get Pinecone index, initializing if needed."""
    global _index
    if _index is None:
        init_pinecone()
    return _index

async def upsert_vectors(
    vectors: list[dict],
    namespace: str = "default",
    batch_size: int = 100
) -> dict:
    """
    Upsert vectors to Pinecone.

    Args:
        vectors: List of {"id": str, "values": list[float], "metadata": dict}
        namespace: Target namespace
        batch_size: Vectors per upsert call

    Returns:
        {"upserted_count": int}
    """
    index = get_index()
    total_upserted = 0

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]

        # Format for Pinecone
        upsert_data = [
            {
                "id": v["id"],
                "values": v["values"],
                "metadata": v.get("metadata", {})
            }
            for v in batch
        ]

        response = index.upsert(vectors=upsert_data, namespace=namespace)
        total_upserted += response.upserted_count

    return {"upserted_count": total_upserted}

async def query_vectors(
    query_embedding: list[float],
    namespace: str = "default",
    top_k: int = 5,
    filter: Optional[dict] = None,
    include_metadata: bool = True
) -> list[dict]:
    """
    Query Pinecone for similar vectors.

    Returns:
        List of {"id", "score", "metadata"} dicts
    """
    index = get_index()

    response = index.query(
        vector=query_embedding,
        namespace=namespace,
        top_k=top_k,
        filter=filter,
        include_metadata=include_metadata
    )

    results = []
    for match in response.matches:
        results.append({
            "id": match.id,
            "score": match.score,
            "metadata": match.metadata or {}
        })

    return results

async def delete_vectors(
    ids: list[str] = None,
    namespace: str = "default",
    delete_all: bool = False,
    filter: Optional[dict] = None
) -> dict:
    """Delete vectors by ID, filter, or all in namespace."""
    index = get_index()

    if delete_all:
        index.delete(delete_all=True, namespace=namespace)
    elif ids:
        index.delete(ids=ids, namespace=namespace)
    elif filter:
        index.delete(filter=filter, namespace=namespace)

    return {"deleted": True}

async def get_index_stats() -> dict:
    """Get index statistics."""
    index = get_index()
    stats = index.describe_index_stats()

    return {
        "total_vector_count": stats.total_vector_count,
        "dimension": stats.dimension,
        "namespaces": {
            ns: {"vector_count": data.vector_count}
            for ns, data in stats.namespaces.items()
        }
    }

async def list_namespaces() -> list[str]:
    """List all namespaces in the index."""
    stats = await get_index_stats()
    return list(stats.get("namespaces", {}).keys())


# Sync wrappers for Celery
def upsert_vectors_sync(vectors: list[dict], namespace: str = "default") -> dict:
    """Synchronous upsert."""
    import asyncio
    return asyncio.run(upsert_vectors(vectors, namespace))
```

---

## 4. Backend Configuration

### Create `backend/config.py`

```python
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional

class Settings(BaseSettings):
    # Required API keys
    openai_api_key: str
    pinecone_api_key: str

    # Pinecone settings
    pinecone_index_name: str = "llm-md-index"
    pinecone_environment: str = "us-east-1"

    # Optional LLM providers
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # Default LLM settings
    default_llm_provider: str = "openai"
    default_llm_model: Optional[str] = None

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: float = 0.2

    # Embedding settings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Redis/Celery settings
    redis_url: str = "redis://localhost:6379/0"

    # Async processing thresholds
    async_file_size_threshold: int = 100_000  # 100KB
    async_chunk_count_threshold: int = 20

    # Logging
    log_level: str = "INFO"

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v):
        if not 0.0 <= v <= 0.5:
            raise ValueError("chunk_overlap must be between 0.0 and 0.5")
        return v

    @field_validator("default_llm_provider")
    @classmethod
    def validate_provider(cls, v):
        if v not in ("openai", "anthropic", "ollama"):
            raise ValueError("provider must be openai, anthropic, or ollama")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton instance
settings = Settings()
```

---

## 5. Logging Configuration

### Create `backend/logging_config.py`

```python
import logging
import sys
from typing import Optional

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging
        json_format: Use JSON format for structured logging
    """
    handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # File handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=handlers
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("pinecone").setLevel(logging.WARNING)

class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)
```

---

## Related Files

- [models.md](./models.md) - Pydantic models for requests/responses
- [backend-api.md](./backend-api.md) - API endpoints using these modules
- [backend-services.md](./backend-services.md) - Higher-level services
- [phase-1-setup-upload.md](./phase-1-setup-upload.md) - Project setup instructions
