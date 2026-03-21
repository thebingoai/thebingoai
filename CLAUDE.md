# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A BI platform with AI-powered dashboards, real-time chat, and multi-database connectivity. Built with FastAPI backend and Nuxt 4 frontend. Features RAG via LangGraph, multi-provider LLM support (OpenAI, Anthropic, Ollama), Supabase authentication, and Celery + Redis for async background processing. SSO authentication is available via the enterprise `bingo-sso-auth` plugin.

## Project Structure
This is a dual-repo setup: community edition and enterprise edition are SEPARATE REPOSITORIES, not separate branches. Enterprise extends community via plugins/overlays. Never assume enterprise features live on a branch.
community edition : /Users/edmundhee/work/github/gruda/bingo
enterprise edition : /Users/edmundhee/work/github/gruda/bingo-enterprise

## Docker
- Enterprise Docker compose uses overlay files. Always check for `docker-compose.enterprise.yml` or similar overlay patterns.
- Use `docker compose` (v2), not `docker-compose` (v1).
- Redis URLs inside Docker network use service names (e.g., `redis://redis:6379`), not `localhost`.
- Always verify compose file paths before running commands.

## Git Operations
- SSH remote URL for this project: [fill in your SSH URL]
- Always complete the full commit-and-push cycle in one go; don't stop after staging.
- Check `git remote -v` before pushing if unsure of remote configuration.

## Working Style section 

### Planning vs Implementation
When asked to implement something, proceed directly to implementation after a brief plan outline. Do not spend the entire session in planning mode unless explicitly asked for a plan only. Avoid over-engineering — prefer simple, pragmatic solutions.

### File Reading
Do not re-read files you have already read in this session. Track what you've explored and avoid redundant exploration. If you need to reference something you already read, use your memory of it.

## Development Setup

### Local Development (Recommended)

```bash
# Start all services — auto-detects database mode from DATABASE_URL in .env
./start.sh

# Access points:
# - Frontend: http://localhost:3000
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Health: http://localhost:8000/health
```

Requirements:
- Docker and Docker Compose must be installed and running
- `.env` configured with required API keys and database URL

`start.sh` auto-detects the database mode from `DATABASE_URL` in `.env`:
- **Supabase (default)**: External DB URL → skips Docker PostgreSQL
- **Local PostgreSQL**: `localhost` or `postgres:` URL → includes Docker PostgreSQL via override compose file



### Database Setup

**Option 1: Supabase (recommended)**
1. Create a Supabase project at https://supabase.com
2. Go to Settings > Database > Connection string > URI
3. Set `DATABASE_URL` in `.env` to the connection pooler URI (port 6543)
4. Optionally set `DATABASE_URL_DIRECT` to the direct connection URI (port 5432) for migrations

**Option 2: Local PostgreSQL**
1. Set `DATABASE_URL=postgresql://llm_user:llm_password@localhost:5432/llm_cli` in `.env`
2. `start.sh` will automatically include Docker PostgreSQL

Migrations run automatically on startup via `alembic upgrade head` in the Dockerfile CMD. When using Supabase, set `DATABASE_URL_DIRECT` to bypass the connection pooler for migrations.

### Backend Only (Docker)

```bash
# Supabase mode (no local PostgreSQL)
docker compose -f docker/local/docker-compose.yml up -d

# Local PostgreSQL mode
docker compose -f docker/local/docker-compose.yml -f docker/local/docker-compose.postgres.yml up -d

# View logs
docker compose -f docker/local/docker-compose.yml logs -f backend

# Rebuild after code changes
docker compose -f docker/local/docker-compose.yml up --build -d
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
- `embedding_dimensions`: **3072** (MUST match Qdrant collection vector size)
- `chunk_size`: 512 tokens, `chunk_overlap`: 0.2 (20%)
- `auth_provider`: "supabase" (default for community; "sso" via enterprise plugin)

**Validation**:
- `chunk_overlap` validated to be 0.0-0.5
- `default_llm_provider` validated against ("openai", "anthropic", "ollama")

### Vector Storage (Qdrant)

Self-hosted Qdrant instance with two collections:
- `documents` — indexed document chunks for RAG
- `memories` — persistent conversation memory vectors

Vector size must be 3072 to match `text-embedding-3-large` embeddings.

### Authentication

The auth system uses a **provider pattern** (`backend/auth/`):
- `factory.py`: Provider registry (built-in + plugin-provided)
- `dependencies.py`: FastAPI dependency for route protection
- `providers/supabase_provider.py`: Community default (Supabase)

**Plugin extensibility**: Auth providers can be registered by plugins via `BingoPlugin.auth_providers()`. The enterprise `bingo-sso-auth` plugin adds SSO support this way.

**Key config**: `AUTH_PROVIDER` env var selects the active provider ("supabase" or "sso").

### API Structure

All routes in `backend/api/routes.py` mounted at `/api` prefix:

**Upload**: `upload.py` - handles both sync and async processing
**Query/Search**: `query.py` - vector search + RAG
**Chat**: `chat.py` - LangGraph-powered RAG with conversation threads
**Jobs**: `jobs.py` - background job status
**Health**: `health.py` - system status (Qdrant, Redis, Celery)

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

3. **Storage**: Upserted to Qdrant with metadata

### Redis Usage

Redis serves **four purposes** (separate DBs):
1. **DB 0**: Job status cache (`backend/services/job_store.py`)
2. **DB 1**: Celery task broker (task queue)
3. **DB 2**: Celery result backend (task results)
4. **DB 4**: Agent mesh communication

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

1. **Embedding dimensions mismatch**: Qdrant collection vector size MUST be 3072 for text-embedding-3-large. Changing embedding model requires recreating collections.

2. **Redis connection**: Three separate DBs. Don't reuse connections across purposes (cache vs broker vs results).

3. **Async vs Sync**: Upload uses sync helpers (_sync suffix) because Celery workers are synchronous. Don't use async/await in Celery tasks.

4. **Namespace isolation**: Searches only return results from specified namespace. Empty namespace results ≠ error.

5. **Conversation memory**: Thread IDs are UUIDs, not session IDs. Each new conversation needs new thread_id. Reusing thread_id continues conversation.

## Configuration Notes

### Required Environment Variables

```bash
OPENAI_API_KEY=sk-...           # Required (embeddings + LLM)
DB_ENCRYPTION_KEY=...           # Required (Fernet key for DB password encryption)
```

### Auth Environment Variables

```bash
AUTH_PROVIDER=supabase          # Default for community (or "sso" with enterprise plugin)
SUPABASE_URL=...                # Supabase project URL
SUPABASE_ANON_KEY=...           # Supabase anon/public key
SUPABASE_JWT_SECRET=...         # JWT secret for token verification
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

1. **Qdrant**: Self-hosted or Qdrant Cloud for production
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

This project has a **codemap MCP server** with pre-indexed code structure, call graphs, and relationships.
Always prefer `codemap_*` tools over grep/read for finding functions, understanding call relationships,
impact analysis, and code exploration — they return structured context in a single call.

**Workflows** (use these for multi-step tasks):

- `/codemap-explore` — understand the project structure and architecture
- `/codemap-find-reusable` — search for existing code to reuse before writing new functions
- `/codemap-impact` — analyze blast radius before refactoring or modifying code
- `/codemap-plan` — create an implementation plan grounded in actual code structure
- `/codemap-health-review` — review code quality and identify what to refactor next
- `/codemap-refresh` — regenerate codemap when source files have changed
<!-- codemap:end -->

