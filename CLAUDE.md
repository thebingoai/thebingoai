# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM-MD-CLI is a RAG (Retrieval-Augmented Generation) system for indexing and querying markdown files using LLMs. It consists of:
- **FastAPI backend** with async job processing (Celery + Redis)
- **CLI tool** (`mdcli`) for file uploads and queries
- **Vector storage** via Pinecone for semantic search
- **Multi-provider LLM support** (OpenAI, Anthropic, Ollama)
- **Conversational memory** using LangGraph

## Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install CLI in development mode
pip install -e .

# Configure environment
cp .env.example .env
# Edit .env with API keys (OPENAI_API_KEY, PINECONE_API_KEY required)
```

### Running the Backend
```bash
# Run backend with auto-reload
uvicorn backend.main:app --reload

# Or use the start script
./start.sh
```

### Docker Deployment
```bash
# Full setup with testing
./docker-test.sh

# Manual control
docker-compose up -d              # Start services
docker-compose logs -f backend    # View logs
docker-compose down               # Stop services
docker-compose up --build -d      # Rebuild after changes
```

### CLI Usage
```bash
# Configure backend URL
mdcli configure backend_url http://localhost:8000

# Show configuration
mdcli config-show

# Upload files
mdcli upload ./notes.md --namespace=personal --tag=project
mdcli upload ./docs/ --recursive

# Query/search
mdcli query "search query" --namespace=default --top-k=5

# RAG chat
mdcli chat "question" --namespace=default --provider=openai

# Check job status
mdcli status <job_id>
```

## Architecture

### Backend Structure

**Core Components:**
- `backend/main.py` - FastAPI app with lifespan management for Pinecone initialization
- `backend/config.py` - Pydantic settings (chunk size, LLM providers, async thresholds)
- `backend/api/routes.py` - Central router aggregating all API endpoints

**API Endpoints (backend/api/):**
- `upload.py` - File upload with sync/async processing based on size thresholds
- `query.py` - Vector search endpoints (POST /query, GET /search)
- `chat.py` - RAG endpoints (POST /ask) with streaming support
- `jobs.py` - Job status tracking for async uploads
- `health.py` - Health checks with detailed status

**Services (backend/services/):**
- `rag.py` - RAG orchestration: embeds query → retrieves context → generates answer
- `job_store.py` - Redis-based job status tracking
- `webhook.py` - Webhook notifications for job completion

**LLM Integration (backend/llm/):**
- `factory.py` - Provider registry and instantiation
- `base.py` - Abstract base class for providers
- `openai_provider.py`, `anthropic_provider.py`, `ollama_provider.py` - Provider implementations
- All providers support both sync chat and streaming via `chat()` and `chat_stream()`

**LangGraph (backend/langgraph/):**
- `runner.py` - Orchestrates RAG workflows with conversation memory
- `nodes.py` - Graph nodes: retrieve_context, generate_response
- `state.py` - ConversationState TypedDict definition
- Uses MemorySaver for conversation history (thread-based)

**Vector & Embedding (backend/vectordb/, backend/embedder/):**
- `pinecone.py` - Pinecone operations (init, upsert, query) with both async and sync methods
- `openai.py` - OpenAI embeddings (text-embedding-3-large, 3072 dimensions)

**Async Processing (backend/tasks/):**
- `upload_tasks.py` - Celery tasks for large file processing
- Triggers when file size > 100KB or chunks > 20
- Supports retry logic and webhook notifications

**Parsing (backend/parser/):**
- `markdown.py` - Markdown chunking with token counting (tiktoken)

### CLI Structure

**Entry Point:**
- `cli/main.py` - Typer CLI with commands: upload, query, chat, status, configure

**Commands (cli/commands/):**
- `upload.py` - File upload with glob/recursive support, local caching
- `query.py` - Vector search queries
- `chat.py` - Interactive RAG chat
- `status.py` - Job status polling

**API Client (cli/api/):**
- `client.py` - BackendClient class wrapping all API calls with error handling

**Configuration:**
- `cli/config.py` - YAML-based config (~/.mdcli/config.yaml)
- Stores: backend_url, webhook_url, default_provider, default_namespace

**Caching (cli/cache/):**
- `index_cache.py` - Local SQLite cache to avoid re-uploading unchanged files

**Resolver (cli/resolver/):**
- `folder_resolver.py` - Recursive file discovery and glob pattern matching

## Key Design Patterns

### Upload Flow
1. Client sends file to POST /api/upload
2. Backend checks file size/chunk count
3. **Sync path**: Process immediately, return result
4. **Async path**: Queue Celery task, return job_id
5. Client polls GET /api/jobs/{job_id} for status

### RAG Flow
1. User question → embed with OpenAI
2. Query Pinecone for top-k relevant chunks
3. Build context from retrieved chunks + sources
4. LangGraph orchestrates: retrieve_context → generate_response
5. LLM generates answer with citations
6. Support for streaming responses via SSE

### Multi-Provider LLM
- Factory pattern in `backend/llm/factory.py`
- Each provider implements `BaseLLMProvider` interface
- Runtime selection via query parameter: `?provider=openai`
- Default provider set in config.py

### Conversation Memory
- LangGraph with MemorySaver checkpointer
- Thread-based: each conversation gets unique thread_id
- State persisted across turns in the same thread
- Endpoints: GET/DELETE /api/conversation/{thread_id}

## Configuration Notes

### Environment Variables (.env)
Required:
- `OPENAI_API_KEY` - For embeddings and LLM (if using OpenAI provider)
- `PINECONE_API_KEY` - For vector storage
- `PINECONE_INDEX_NAME` - Index name (default: llm-md-index)
- `PINECONE_ENVIRONMENT` - Region (default: us-east-1)

Optional:
- `ANTHROPIC_API_KEY` - For Claude models
- `OLLAMA_BASE_URL` - For local Ollama (default: http://localhost:11434)
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_URL` - For async processing

### Chunking Settings
- `CHUNK_SIZE=512` - Tokens per chunk
- `CHUNK_OVERLAP=0.2` - Overlap ratio (0.0-0.5)

### Async Thresholds
- `ASYNC_FILE_SIZE_THRESHOLD=100000` - 100KB file size
- `ASYNC_CHUNK_COUNT_THRESHOLD=20` - 20 chunks

## Docker Architecture

Services:
- **backend** (port 8000) - FastAPI app
- **redis** (port 6379) - Job queue & cache
- **celery-worker** - Background task processing

All services share the same `.env` file for configuration.

## Python Version

Requires Python 3.9+ (compatible with 3.10+). The codebase uses:
- Type hints with `dict[str, Any]` syntax (3.9+)
- Pydantic v2 for validation
- AsyncIO throughout for I/O operations
