# LLM-MD-CLI

A FastAPI-based backend for indexing and querying markdown files using LLMs, with a Nuxt frontend (in development).

## Overview

This project provides:
- FastAPI backend for uploading and indexing markdown files
- Pinecone vector storage for semantic search
- OpenAI embeddings and LLM integration
- LangGraph-powered RAG chat with conversation memory
- Celery + Redis for async background processing
- Nuxt 4 frontend (currently in development)

## Architecture

```
┌──────────────┐      HTTP/REST     ┌─────────────────┐
│ Nuxt Frontend│ ◄─────────────────► │  FastAPI Backend│
│ (Port 3000)  │                     │   (Port 8000)   │
└──────────────┘                     └────────┬────────┘
                                              │
                        ┌─────────────────────┼────────────────┐
                        │                     │                │
                        ▼                     ▼                ▼
                  ┌──────────┐          ┌─────────┐     ┌──────────┐
                  │ Pinecone │          │  Redis  │     │  Celery  │
                  │(Vectors) │          │ (Queue) │     │ (Worker) │
                  └──────────┘          └─────────┘     └──────────┘
```

## Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys (OpenAI, Pinecone)
```

## Running the Backend

```bash
# Using uvicorn directly
uvicorn backend.main:app --reload

# Or using the start script (includes Redis + Celery)
./start.sh
```

The backend will be available at `http://localhost:8000`.

Interactive API documentation: `http://localhost:8000/docs`

## Docker Deployment

See [DOCKER.md](DOCKER.md) for Docker deployment instructions.

## API Endpoints

### Upload & Indexing
- `POST /api/upload` - Upload and index markdown files (async with job tracking)

### Search & Query
- `POST /api/query` - Query indexed documents with natural language
- `GET /api/search` - Search indexed documents (returns raw results)

### RAG Chat
- `POST /api/ask` - Chat with RAG using LangGraph (supports conversation threads)
- `GET /api/providers` - List available LLM providers (OpenAI, Anthropic)

### Conversation Management
- `GET /api/conversation/{thread_id}` - Get conversation history
- `DELETE /api/conversation/{thread_id}` - Delete conversation thread

### System & Monitoring
- `GET /health` - Health check endpoint
- `GET /api/status` - Detailed system status (Pinecone, Redis, Celery)
- `GET /api/jobs` - List all background jobs
- `GET /api/jobs/{job_id}` - Get specific job status

## Project Structure

```
llm-cli/
├── backend/          # FastAPI application
│   ├── api/         # API route handlers
│   ├── langgraph/   # LangGraph RAG implementation
│   ├── services/    # Core services (embeddings, indexing)
│   └── tasks/       # Celery background tasks
├── frontend/        # Nuxt 4 frontend (in development)
├── test_data/       # Sample markdown files for testing
├── docker-compose.yml
├── Dockerfile
└── start.sh        # Local development startup script
```

## Requirements

- Python 3.9+
- OpenAI API key
- Pinecone API key (with serverless index)
- Redis (for background jobs)

## Development Status

- ✅ Backend API complete
- ✅ RAG chat with LangGraph
- ✅ Async job processing
- ✅ Docker deployment
- 🚧 Nuxt frontend (in progress)

## Backend Flow

This section provides detailed flow diagrams for all major backend features.

### 1. Upload Funnel

```
POST /api/upload (with file + optional namespace)
│
├─► Receive multipart/form-data
│   ├─ file: markdown file
│   ├─ namespace: string (optional, default: "default")
│   └─ tags: array (optional)
│
├─► Parse markdown file
│   └─► backend/parser/markdown.py::chunk_markdown()
│       ├─ Split on headers first
│       ├─ Then split by token count (chunk_size: 512)
│       └─ Apply overlap (20% = ~102 tokens)
│
├─► Decision: Sync or Async?
│   ├─ Condition: file_size > 100KB OR chunk_count > 20
│   │
│   ├─► [ASYNC PATH]
│   │   │
│   │   ├─► Create job in Redis
│   │   │   └─ backend/services/job_store.py
│   │   │       ├─ job_id: UUID
│   │   │       ├─ status: "PENDING"
│   │   │       ├─ chunks_total: count
│   │   │       └─ TTL: 7 days
│   │   │
│   │   ├─► Queue Celery task
│   │   │   └─ backend/tasks/upload_tasks.py::process_upload_async()
│   │   │       └─ Sent to Redis DB 1 (broker)
│   │   │
│   │   └─► Return immediately
│   │       └─ Response: {"job_id": "...", "status": "pending"}
│   │
│   └─► [SYNC PATH]
│       │
│       └─► Process immediately
│           └─ (continues to embedding flow below)
│
├─► Embedding Flow (runs in Celery worker for async, main thread for sync)
│   │
│   ├─► Update job status → "PROCESSING" (async only)
│   │
│   ├─► Generate embeddings
│   │   └─► backend/embedder/openai.py::embed_chunks()
│   │       ├─ Model: text-embedding-3-large
│   │       ├─ Batch size: 100 chunks
│   │       ├─ Output dimensions: 3072
│   │       └─ Update progress: chunks_processed / chunks_total
│   │
│   └─► Store in Pinecone
│       └─► backend/services/indexer.py::index_chunks()
│           ├─ Namespace: from request or "default"
│           ├─ Vector format:
│           │   ├─ id: "{filename}#chunk-{index}"
│           │   ├─ values: [3072-dim embedding]
│           │   └─ metadata:
│           │       ├─ source: filename
│           │       ├─ chunk_index: int
│           │       ├─ text: chunk content
│           │       ├─ tags: array
│           │       └─ created_at: ISO timestamp
│           └─ Upsert batch (100 vectors at a time)
│
└─► Final Response
    ├─► [ASYNC]: Return job_id immediately
    │   └─ Client polls GET /api/jobs/{job_id}
    │
    └─► [SYNC]: Return completion status
        └─ Response: {"status": "completed", "chunks_indexed": N}
```

### 2. Chat/Ask Funnel (LangGraph RAG)

```
POST /api/ask
│
├─► Request body (backend/models/requests.py::AskRequest)
│   ├─ question: string (required, 1-10000 chars)
│   ├─ namespace: string (default: "default")
│   ├─ top_k: int (1-20, default: 5)
│   ├─ provider: string ("openai"|"anthropic"|"ollama", default: "openai")
│   ├─ model: string (optional, provider-specific override)
│   ├─ temperature: float (0.0-2.0, default: 0.7)
│   ├─ stream: bool (default: false)
│   └─ thread_id: string (optional UUID, for conversation continuity)
│
├─► Route handler (backend/api/chat.py::ask)
│   └─ Calls run_rag_query() with stream=false (non-streaming path)
│
├─► RAG orchestrator (backend/langgraph/runner.py::run_rag_query)
│   ├─ If thread_id is None → generate new UUID
│   └─ Calls _run_sync() → graph.ainvoke(initial_state, config)
│       ├─ initial_state: ConversationState dict
│       └─ config: {"configurable": {"thread_id": UUID}}
│           └─ MemorySaver uses thread_id for checkpoint lookup
│
├─► LangGraph State (backend/langgraph/state.py)
│   └─ ConversationState(TypedDict):
│       ├─ messages: Annotated[Sequence[BaseMessage], add_messages]
│       │   └─ add_messages reducer: new messages APPEND, never replace
│       ├─ question, namespace, provider, model, temperature, top_k
│       ├─ context: List[dict]    (filled by retrieve_context)
│       ├─ sources: List[ContextSource]  (filled by retrieve_context)
│       ├─ has_context: bool      (filled by retrieve_context)
│       ├─ answer: Optional[str]  (filled by generate_response)
│       └─ thread_id: str
│
├─► Graph topology (backend/langgraph/nodes.py::create_rag_graph)
│   │
│   │   START ──► retrieve_context ──► [should_generate] ──► generate_response ──► END
│   │                                        │
│   │                              Both "generate" and "no_context"
│   │                              route to the SAME node
│   │
│   ├─► NODE 1: retrieve_context (nodes.py)
│   │   │
│   │   ├─► Embed the question
│   │   │   └─ backend/embedder/openai.py::embed_text(question)
│   │   │       ├─ Model: text-embedding-3-large (always OpenAI, regardless of chat provider)
│   │   │       ├─ Output: 3072-dim vector
│   │   │       └─ Retry: up to 3x on RateLimitError or 5xx errors
│   │   │
│   │   ├─► Query Pinecone
│   │   │   └─ backend/vectordb/pinecone.py::query_vectors()
│   │   │       ├─ vector: 3072-dim embedding
│   │   │       ├─ namespace: from request
│   │   │       ├─ top_k: from request (default 5)
│   │   │       └─ Runs in thread pool (asyncio.to_thread)
│   │   │
│   │   ├─► Process results
│   │   │   ├─ context[]: [{source, chunk_index, text, score}...]
│   │   │   └─ sources[]: [{source, chunk_index, score}...] (score rounded to 4 decimals)
│   │   │
│   │   └─► Determine has_context
│   │       └─ has_context = len(context) > 0 AND context[0].score > 0.5
│   │           └─ Score threshold: settings.rag_context_score_threshold (default: 0.5)
│   │
│   ├─► CONDITIONAL EDGE: should_generate (nodes.py)
│   │   ├─ If has_context → "generate"     ─┐
│   │   └─ If not         → "no_context"   ─┤► Both route to generate_response
│   │
│   └─► NODE 2: generate_response (nodes.py)
│       │
│       ├─► Select system prompt (based on context list, not has_context flag)
│       │   │
│       │   ├─► [context non-empty] → SYSTEM_PROMPT (backend/prompts.py)
│       │   │   └─ "You are a helpful assistant that answers questions
│       │   │      based on the user's personal notes and documents..."
│       │   │      + formatted context chunks:
│       │   │        [Source: {source}, Section {chunk_index}]
│       │   │        {text}
│       │   │
│       │   └─► [context empty] → NO_CONTEXT_PROMPT (backend/prompts.py)
│       │       └─ "No relevant documents were found in their indexed files..."
│       │
│       ├─► Get LLM provider
│       │   └─ backend/llm/factory.py::get_provider(provider, model)
│       │       ├─ OpenAI  → default model: gpt-4o
│       │       ├─ Anthropic → default model: claude-sonnet-4-20250514
│       │       └─ Ollama  → default model: llama3.2
│       │
│       ├─► Build LLM messages (with conversation history)
│       │   └─ Final message order:
│       │       ├─ [0] system: selected prompt (with or without context)
│       │       ├─ [1..N] history: last 6 messages from prior turns
│       │       │   └─ From state["messages"] (populated via MemorySaver checkpoint)
│       │       │       └─ Inserted before current question, after system prompt
│       │       └─ [last] user: current question
│       │
│       ├─► Call LLM
│       │   └─ provider.chat(llm_messages, temperature=temperature)
│       │       └─ Non-streaming call → returns full answer string
│       │
│       └─► Update state
│           ├─ answer: LLM response text
│           └─ messages: [HumanMessage(question), AIMessage(answer)]
│               └─ add_messages reducer APPENDS these to existing history
│
├─► Checkpoint
│   └─ MemorySaver saves full state for this thread_id
│       └─ Next call with same thread_id resumes conversation
│
└─► Response (backend/models/responses.py::AskResponse)
    ├─ answer: string (LLM response)
    ├─ sources: [{source, chunk_index, score}...]
    ├─ provider: string (e.g. "openai")
    ├─ model: string (e.g. "gpt-4o")
    ├─ thread_id: string (UUID for conversation continuity)
    └─ has_context: bool (true if top result scored > 0.5)
```

**Conversation Memory:**
- Each `thread_id` maintains independent conversation history via LangGraph's `MemorySaver`
- The `add_messages` reducer automatically appends new messages to history (never replaces)
- Last 6 messages from history are included in each LLM call
- State is **in-memory only** — lost on process restart, not shared across workers
- To continue a conversation: send the same `thread_id` in subsequent requests
- To start fresh: omit `thread_id` (a new UUID is generated)

### 3. Search/Query Funnel

```
POST /api/query  OR  GET /api/search
│
├─► Request parameters
│   ├─ query: string (natural language question)
│   ├─ namespace: string (optional, default: "default")
│   ├─ top_k: int (optional, default: 5)
│   └─ [/api/query only] include_answer: bool (optional, LLM summary)
│
├─► Generate query embedding
│   └─► backend/embedder/openai.py::embed_text()
│       ├─ Model: text-embedding-3-large
│       └─ Output: [3072-dim vector]
│
├─► Query Pinecone
│   └─► backend/services/retriever.py::search()
│       ├─ Input:
│       │   ├─ query_vector: [3072 floats]
│       │   ├─ namespace: from request
│       │   └─ top_k: from request
│       │
│       └─ Returns: matches
│           └─ Each match:
│               ├─ id: "{filename}#chunk-{index}"
│               ├─ score: 0.0-1.0 (cosine similarity)
│               └─ metadata: {source, text, chunk_index, tags}
│
├─► Format results
│   └─ Extract and structure:
│       ├─ source: filename
│       ├─ text: chunk content
│       ├─ score: similarity score
│       └─ chunk_index: position in document
│
└─► Response
    ├─► [GET /api/search]: Raw results
    │   └─ [{source, text, score, chunk_index}...]
    │
    └─► [POST /api/query]: Optionally add LLM summary
        ├─ If include_answer=true:
        │   ├─ Build prompt with retrieved context
        │   ├─ Call LLM provider
        │   └─ Add "answer" field to response
        │
        └─ Response:
            ├─ results: [{source, text, score}...]
            └─ answer: string (if requested)
```

### 4. Job Tracking Funnel

```
Background Job Lifecycle (Async Upload)
│
├─► Job Creation (at upload time)
│   └─► backend/services/job_store.py::create_job()
│       ├─ Generate job_id: UUID
│       ├─ Store in Redis DB 0:
│       │   ├─ Key: "job:{job_id}"
│       │   ├─ Value: JSON
│       │   │   ├─ job_id: string
│       │   │   ├─ status: "PENDING"
│       │   │   ├─ filename: string
│       │   │   ├─ namespace: string
│       │   │   ├─ chunks_total: int
│       │   │   ├─ chunks_processed: 0
│       │   │   ├─ created_at: ISO timestamp
│       │   │   └─ updated_at: ISO timestamp
│       │   └─ TTL: 7 days (604800 seconds)
│       │
│       └─ Return job_id to client
│
├─► Job Processing (in Celery worker)
│   │
│   ├─► Update: status → "PROCESSING"
│   │   └─ backend/services/job_store.py::update_job()
│   │
│   ├─► Progress updates (during embedding)
│   │   └─ For each batch:
│   │       ├─ chunks_processed += batch_size
│   │       ├─ Calculate progress: (processed / total) * 100
│   │       └─ Update Redis job record
│   │
│   ├─► Completion: status → "COMPLETED"
│   │   └─ Update:
│   │       ├─ status: "COMPLETED"
│   │       ├─ chunks_processed: chunks_total
│   │       ├─ completed_at: ISO timestamp
│   │       └─ result: {chunks_indexed, namespace}
│   │
│   └─► Error handling: status → "FAILED"
│       └─ Update:
│           ├─ status: "FAILED"
│           ├─ error: error message
│           └─ failed_at: ISO timestamp
│
├─► Client Polling
│   │
│   ├─► GET /api/jobs/{job_id}
│   │   └─► backend/api/jobs.py::get_job_status()
│   │       ├─ Fetch from Redis: "job:{job_id}"
│   │       └─ Return:
│   │           ├─ job_id: string
│   │           ├─ status: PENDING|PROCESSING|COMPLETED|FAILED
│   │           ├─ progress: 0-100 (percentage)
│   │           ├─ chunks_processed: int
│   │           ├─ chunks_total: int
│   │           └─ result: object (if completed)
│   │
│   └─► GET /api/jobs (list all)
│       └─► backend/api/jobs.py::list_jobs()
│           ├─ Scan Redis: "job:*" pattern
│           └─ Return array of all job statuses
│
└─► Cleanup
    └─ Redis auto-expires after 7 days (TTL)
```

**Celery Configuration:**
- **Broker**: Redis DB 1 (`redis://redis:6379/1`)
- **Result Backend**: Redis DB 2 (`redis://redis:6379/2`)
- **Task Retry Policy**:
  - Max retries: 3
  - Backoff: exponential (60s, 120s, 240s)
  - Max task time: 1 hour

### 5. Health Check Funnel

```
System Health Monitoring
│
├─► GET /health (Basic health check)
│   └─► backend/api/health.py::health_check()
│       ├─ Always returns 200 OK
│       └─ Response: {"status": "healthy", "timestamp": ISO}
│
├─► GET /api/status (Detailed system status)
│   └─► backend/api/health.py::system_status()
│       │
│       ├─► Check Pinecone
│       │   └─ backend/services/pinecone_client.py::health_check()
│       │       ├─ Try: index.describe_index_stats()
│       │       ├─ Success: {"status": "healthy", "vector_count": N}
│       │       └─ Failure: {"status": "unhealthy", "error": "..."}
│       │
│       ├─► Check Redis
│       │   └─ backend/services/job_store.py::health_check()
│       │       ├─ Try: redis.ping()
│       │       ├─ Success: {"status": "healthy"}
│       │       └─ Failure: {"status": "unhealthy", "error": "..."}
│       │
│       ├─► Check Celery
│       │   └─ backend/tasks/upload_tasks.py::health_check()
│       │       ├─ Try: celery.control.inspect().active()
│       │       ├─ Success: {"status": "healthy", "workers": N}
│       │       └─ Failure: {"status": "unhealthy", "error": "..."}
│       │
│       └─► Aggregate response
│           └─ Response:
│               ├─ overall_status: "healthy" | "degraded" | "unhealthy"
│               ├─ services:
│               │   ├─ pinecone: {...}
│               │   ├─ redis: {...}
│               │   └─ celery: {...}
│               └─ timestamp: ISO
│
└─► GET /api/providers (LLM provider availability)
    └─► backend/api/chat.py::list_providers()
        │
        ├─► Check each provider
        │   ├─► OpenAI
        │   │   └─ Check: OPENAI_API_KEY in env
        │   │       └─ available: true/false
        │   │
        │   ├─► Anthropic
        │   │   └─ Check: ANTHROPIC_API_KEY in env
        │   │       └─ available: true/false
        │   │
        │   └─► Ollama
        │       └─ Check: HTTP GET to OLLAMA_BASE_URL
        │           └─ available: true/false
        │
        └─► Response:
            └─ providers: [
                {name: "openai", available: bool, models: [...]},
                {name: "anthropic", available: bool, models: [...]},
                {name: "ollama", available: bool, models: [...]}
              ]
```

### 6. External Service Dependency Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Nuxt 4)                           │
│                         Port: 3000 (dev)                            │
│                    [Currently in development]                       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTP/REST (CORS configured)
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                    FASTAPI BACKEND (main.py)                        │
│                         Port: 8000                                  │
│                                                                     │
│  API Routes (backend/api/routes.py):                               │
│  ├─ /api/upload     → upload.py                                    │
│  ├─ /api/query      → query.py                                     │
│  ├─ /api/ask        → chat.py (LangGraph)                          │
│  ├─ /api/search     → query.py                                     │
│  ├─ /api/jobs       → jobs.py                                      │
│  └─ /health, /api/status → health.py                               │
└──┬────────────┬────────────┬────────────┬─────────────────────────┘
   │            │            │            │
   │            │            │            │
   ▼            ▼            ▼            ▼
┌──────────┐ ┌─────────┐ ┌────────────┐ ┌──────────────────────────┐
│ PINECONE │ │  REDIS  │ │  CELERY    │ │   OPENAI API             │
│ (Vector  │ │ (Cache  │ │ (Worker)   │ │   (LLM + Embeddings)     │
│  Store)  │ │ + Queue)│ │            │ │                          │
│          │ │         │ │            │ │   Anthropic API          │
│  Index:  │ │ 3 DBs:  │ │ Queue:     │ │   (LLM - optional)       │
│  ├─ 3072 │ │ ├─ DB 0:│ │ Redis DB 1 │ │                          │
│  │  dims │ │ │  Jobs │ │            │ │   Ollama                 │
│  └─ NS:  │ │ ├─ DB 1:│ │ Results:   │ │   (Local LLM - optional) │
│     ├─def│ │ │  Broker│ │ Redis DB 2 │ │                          │
│     └─...│ │ └─ DB 2:│ │            │ │                          │
│          │ │    Results│ │ Tasks:     │ │                          │
│          │ │         │ │ └─ upload  │ │                          │
└──────────┘ └─────────┘ └────────────┘ └──────────────────────────┘
     │            │            │                  │
     │            │            │                  │
     └────────────┴────────────┴──────────────────┘
                  │
                  ▼
          ┌──────────────────┐
          │  Configuration   │
          │  (backend/       │
          │   config.py)     │
          │                  │
          │  Environment:    │
          │  ├─ .env file    │
          │  └─ docker-      │
          │     compose.yml  │
          └──────────────────┘
```

**Service Communication:**

1. **Frontend ↔ Backend**: HTTP/REST
   - Development: `localhost:3000` → `localhost:8000`
   - CORS configured in `backend/main.py`

2. **Backend → Pinecone**: Python SDK
   - Vector operations: upsert, query
   - Namespace-based organization
   - Serverless index (3072 dimensions)

3. **Backend → Redis**: `redis-py`
   - **DB 0**: Job status cache (job_store.py)
   - **DB 1**: Celery task broker
   - **DB 2**: Celery result backend

4. **Backend → Celery**: Task queue
   - Tasks: `backend/tasks/upload_tasks.py`
   - Worker runs independently
   - Async processing for large uploads

5. **Backend → OpenAI**: `openai` Python SDK
   - Embeddings: `text-embedding-3-large` (3072 dims)
   - Chat: `gpt-4`, `gpt-3.5-turbo`, etc.

6. **Backend → Anthropic**: `anthropic` Python SDK (optional)
   - Chat: `claude-3-opus`, `claude-3-sonnet`, etc.
   - Requires `ANTHROPIC_API_KEY`

7. **Backend → Ollama**: HTTP API (optional)
   - Local LLM inference
   - Default: `http://localhost:11434`

**Configuration Sources:**
- Primary: `.env` file (development)
- Override: `docker-compose.yml` environment vars (Docker)
- Validation: `backend/config.py` (Pydantic Settings)
