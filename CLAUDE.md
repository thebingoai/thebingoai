# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FastAPI backend for indexing and querying markdown files using LLMs, with Nuxt 4 frontend (in development). The backend provides RAG capabilities using LangGraph, supports multiple LLM providers (OpenAI, Anthropic, Ollama), and uses Celery + Redis for async background processing.

## Development Setup

### Local Development (Recommended)

```bash
# Start all services (Docker backend + native frontend)
./start.sh

# Access points:
# - Frontend: http://localhost:3000
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

Requirements:
- Docker and Docker Compose must be installed and running
- Node.js must be installed (for the frontend)
- `.env` configured with required API keys

`start.sh` runs `docker-compose up -d` for all backend services (Postgres, Redis, Qdrant, backend, celery-worker), waits for the health check, then starts the Nuxt frontend natively with `npm run dev`. Ctrl+C stops everything.

### Backend Only (Docker)

```bash
# Start backend services without the frontend
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Rebuild after code changes
docker-compose up --build -d
```

### Manual Setup (Advanced)

```bash
# Backend only (requires local Postgres, Redis, Qdrant)
uvicorn backend.main:app --reload

# Celery worker (in separate terminal)
celery -A backend.tasks.upload_tasks worker --loglevel=info
```

## Architecture

### Multi-Provider LLM System

The system uses a **factory pattern** for LLM providers (`backend/llm/`):

- `factory.py`: Provider registry and instantiation
- `base.py`: `BaseLLMProvider` abstract class defining interface
- `openai_provider.py`, `anthropic_provider.py`, `ollama_provider.py`: Concrete implementations

**Key pattern**: All providers implement `chat()` and `chat_stream()` methods. To add a new provider:
1. Extend `BaseLLMProvider`
2. Register in `factory.py` via `_PROVIDERS` dict
3. Add availability check logic in provider class

Default provider set via `settings.default_llm_provider` (config.py).

### LangGraph RAG Workflow

The RAG system (`backend/langgraph/`) uses LangGraph for stateful conversation:

**Architecture**:
- `state.py`: Defines `ConversationState` TypedDict with `messages` using LangGraph's `add_messages` reducer for automatic history management
- `nodes.py`: Graph nodes (retrieve, check_context, generate, generate_no_context)
- `runner.py`: Orchestrates graph execution with checkpointing for conversation threads

**Critical details**:
- **Thread-based memory**: Each conversation has a `thread_id`. LangGraph's `MemorySaver` checkpoints state between turns
- **State flow**: retrieve → check_context → (generate OR generate_no_context) based on whether context was found
- **Streaming**: Currently simplified (runner.py:115-211) - runs full graph, then streams LLM response. For true streaming, would need LangGraph's native streaming support

**Conversation management**:
- Thread IDs are UUIDs stored in Redis with 7-day TTL
- History retrieval (get_conversation_history) is currently limited - proper implementation would need checkpoint deserialization

### Async Processing with Celery

Upload processing (`backend/tasks/upload_tasks.py`) uses Celery for large files:

**Decision logic** (in `backend/api/upload.py`):
- Files > 100KB OR > 20 chunks → async processing
- Smaller files → synchronous processing

**Job tracking**:
- Jobs stored in Redis via `backend/services/job_store.py`
- Each job has: `job_id`, status (pending/running/completed/failed), progress %, chunks_processed, chunks_total
- Frontend can poll `GET /api/jobs/{job_id}` for progress

**Celery configuration**:
- 3 separate Redis DBs: 0=cache, 1=broker, 2=results (see docker-compose.yml)
- Max task time: 1 hour
- Retry policy: 3 retries with exponential backoff (60s, 120s, 240s)

### Configuration Management

All config in `backend/config.py` using Pydantic Settings:

**Critical settings**:
- `embedding_model`: "text-embedding-3-large" (default)
- `embedding_dimensions`: **3072** (MUST match Pinecone index dimensions)
- `chunk_size`: 512 tokens, `chunk_overlap`: 0.2 (20%)
- `pinecone_index_name`: Namespace-based organization within single index

**Validation**:
- `chunk_overlap` validated to be 0.0-0.5
- `default_llm_provider` validated against ("openai", "anthropic", "ollama")

### Vector Storage (Pinecone)

**Organization**: Single index with namespace-based separation
- Upload: `POST /api/upload` with optional `namespace` param (default: "default")
- Query: Specify `namespace` in search/query requests

**Vector format**:
```python
{
    "id": f"{file_name}#chunk-{index}",
    "values": [3072-dim embedding],
    "metadata": {
        "source": file_name,
        "chunk_index": i,
        "text": chunk_text,
        "tags": [...],
        "created_at": ISO timestamp
    }
}
```

**Important**: Pinecone index must be serverless (not pod-based) with 3072 dimensions for text-embedding-3-large.

### API Structure

All routes in `backend/api/routes.py` mounted at `/api` prefix:

**Upload**: `upload.py` - handles both sync and async processing
**Query/Search**: `query.py` - vector search + RAG
**Chat**: `chat.py` - LangGraph-powered RAG with conversation threads
**Jobs**: `jobs.py` - background job status
**Health**: `health.py` - system status (Pinecone, Redis, Celery)

### Frontend Integration

Frontend (`frontend/`) is a **separate Nuxt 4 application** (currently in development):
- Backend exposes REST API only (no server-side rendering of frontend)
- Communication via HTTP/REST on port 8000 (backend) and 3000 (frontend dev server)
- CORS configured in `backend/main.py` if needed

## Key Technical Details

### Embedding Pipeline

1. **Chunking** (`backend/parser/markdown.py`):
   - Splits markdown on headers first, then by token count
   - Overlap calculated as fraction of chunk_size (e.g., 0.2 * 512 = ~102 tokens)

2. **Embedding** (`backend/embedder/openai.py`):
   - Batch processing (default: 100 chunks per batch)
   - Uses OpenAI's `text-embedding-3-large` model
   - Returns 3072-dimensional vectors

3. **Storage**: Upserted to Pinecone with metadata

### Redis Usage

Redis serves **three purposes** (3 separate DBs):
1. **DB 0**: Job status cache (`backend/services/job_store.py`)
2. **DB 1**: Celery task broker (task queue)
3. **DB 2**: Celery result backend (task results)

Connection strings in docker-compose.yml override `.env` when running in Docker.

### Logging

Structured logging via `backend/logging_config.py`:
- Format: `YYYY-MM-DD HH:MM:SS | LEVEL | module:line | message`
- Level controlled by `settings.log_level` (default: INFO)
- All modules use: `logger = logging.getLogger(__name__)`

## Important Patterns

### Adding a New API Endpoint

1. Create handler in appropriate `backend/api/*.py` file
2. Add route in `backend/api/routes.py`
3. Use async def for all handlers
4. Import dependencies at function level if they're slow (e.g., LLM providers)

### Adding a New LLM Provider

1. Create `backend/llm/{provider}_provider.py`
2. Extend `BaseLLMProvider`
3. Implement `chat()` and `chat_stream()` methods
4. Add to `_PROVIDERS` in `factory.py`
5. Add API key to Settings if needed

### Modifying Chunking Strategy

Edit `backend/parser/markdown.py`:
- `chunk_markdown()`: Main chunking logic
- Consider chunk_size and chunk_overlap from settings
- Maintain metadata (chunk_index, source) for traceability

### Working with LangGraph State

The `ConversationState` in `state.py` uses LangGraph's `add_messages` reducer:
- **Never** manually append to messages list
- **Do** return new messages from nodes - LangGraph merges automatically
- Thread-based checkpointing means state persists across invocations with same thread_id

## Common Pitfalls

1. **Embedding dimensions mismatch**: Pinecone index MUST be 3072 dims for text-embedding-3-large. Changing embedding model requires new index.

2. **Redis connection**: Three separate DBs. Don't reuse connections across purposes (cache vs broker vs results).

3. **Async vs Sync**: Upload uses sync helpers (_sync suffix) because Celery workers are synchronous. Don't use async/await in Celery tasks.

4. **Namespace isolation**: Searches only return results from specified namespace. Empty namespace results ≠ error.

5. **Conversation memory**: Thread IDs are UUIDs, not session IDs. Each new conversation needs new thread_id. Reusing thread_id continues conversation.

## Configuration Notes

### Required Environment Variables

```bash
OPENAI_API_KEY=sk-...           # Required
PINECONE_API_KEY=...            # Required
PINECONE_INDEX_NAME=...         # Required (must exist, 3072 dims)
```

### Optional Environment Variables

```bash
ANTHROPIC_API_KEY=...           # For Anthropic provider
OLLAMA_BASE_URL=...             # For Ollama (default: http://localhost:11434)
DEFAULT_LLM_PROVIDER=...        # openai|anthropic|ollama (default: openai)
DEFAULT_LLM_MODEL=...           # Model override
REDIS_URL=...                   # Default: redis://localhost:6379/0
LOG_LEVEL=...                   # DEBUG|INFO|WARNING|ERROR (default: INFO)
```

## Deployment

### Production Considerations

1. **Pinecone**: Use serverless index for cost efficiency
2. **Redis**: Consider Redis Cloud or AWS ElastiCache for production
3. **Celery**: Run multiple workers for parallel processing
4. **Monitoring**: Enable health check endpoints (`/health`, `/api/status`)
5. **Rate Limits**: OpenAI embedding API has rate limits - consider retry logic
6. **CORS**: Configure allowed origins in `backend/main.py` if frontend on different domain

### Docker Production

- Use environment-specific `.env` files
- Set `DEBUG=false`
- Configure proper CORS origins
- Use reverse proxy (nginx) for SSL termination
- Scale Celery workers: `docker-compose up -d --scale celery-worker=3`

<!-- codemap:start -->
## Codemap

This project uses **codemap** for static analysis. A codemap MCP server is available
that provides pre-indexed project structure, call graphs, and relationships.

**Always prefer codemap MCP tools over grep/read for code exploration:**

- `codemap_overview` — project summary: modules, frameworks, languages, file counts
- `codemap_module` — all classes, functions, imports for a specific directory
- `codemap_query` — search by name (exact + fuzzy) across the entire codebase
- `codemap_callers` — find all callers of a function (impact analysis)
- `codemap_calls` — find all functions called by a function (dependency tracing)
- `codemap_projects` — list all registered projects (multi-project setups)

These return structured context in a single call instead of multiple file reads.
Use `codemap_overview` first to understand the project, then drill into specific
modules or functions as needed.
<!-- codemap:end -->
