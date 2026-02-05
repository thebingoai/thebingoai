# LLM-MD-CLI Implementation Plan

## Project Overview

A CLI tool that connects to a backend service for indexing Markdown files with vector embeddings and querying via multiple LLM providers.

## Confirmed Requirements

Based on our discussion, this plan is built for:

| Requirement | Decision |
|-------------|----------|
| Authentication | No auth for MVP (add later) |
| Async Processing | Redis + Celery background queue |
| Completion Notification | Webhook URL (user provides callback) |
| LLM Providers | Multi-provider: OpenAI, Anthropic, Ollama |
| Deployment | Docker Compose (local/self-hosted) |
| Testing | Skip for MVP |

---

## Phase Overview

| Phase | Focus | Duration | Key Deliverables |
|-------|-------|----------|------------------|
| [Phase 1](./phase-1-setup-upload.md) | Project Setup & Upload | Week 1 | FastAPI backend, Pinecone integration, CLI upload |
| [Phase 2](./phase-2-query-search.md) | Query & Search | Week 2 | Vector search API, CLI query command |
| [Phase 2.5](./phase-2.5-interactive-chat.md) | **Interactive Chat Mode** | Week 2-3 | Claude Code-style REPL, @folder references, index cache |
| [Phase 3](./phase-3-chat-rag.md) | Chat & RAG | Week 3 | Multi-provider LLM, RAG pipeline, CLI ask |
| [Phase 4](./phase-4-async-webhooks.md) | Async & Webhooks | Week 4a | Celery workers, job queue, webhook notifications |
| [Phase 5](./phase-5-docker-deployment.md) | Docker & Deploy | Week 4b | Containerization, Docker Compose |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User's Machine                          │
│  ┌─────────┐                                                    │
│  │  mdcli  │ ◄── CLI tool                                       │
│  └────┬────┘                                                    │
│       │ HTTP                                                    │
└───────┼─────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                         │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────┐  │
│  │   FastAPI    │───►│  Celery Worker  │───►│     Redis     │  │
│  │   Backend    │◄───│                 │◄───│               │  │
│  └──────┬───────┘    └────────┬────────┘    └───────────────┘  │
│         │                     │                                 │
└─────────┼─────────────────────┼─────────────────────────────────┘
          │                     │
          ▼                     ▼
    ┌───────────┐         ┌───────────┐
    │  Pinecone │         │   OpenAI  │
    │  (Vectors)│         │ Anthropic │
    └───────────┘         │  Ollama   │
                          └───────────┘
```

---

## Tech Stack Summary

### Backend
- **Framework:** FastAPI (async, auto-docs)
- **RAG Workflow:** LangGraph (stateful, conversation memory)
- **Task Queue:** Celery + Redis
- **Embeddings:** OpenAI text-embedding-3-large (3072 dims)
- **Vector DB:** Pinecone
- **LLM Providers:** OpenAI, Anthropic, Ollama

### CLI
- **Framework:** Typer + Rich
- **HTTP Client:** httpx
- **Config:** YAML file (~/.mdcli/config.yaml)

### Infrastructure
- **Containerization:** Docker
- **Orchestration:** Docker Compose
- **Message Broker:** Redis

---

## CLI Commands (Final)

### Primary Mode: Interactive Chat (Claude Code-style)

```bash
$ mdcli chat

You: @my-notes What did I learn about embeddings?

📁 Folder 'my-notes' not indexed. Index it now? [Y/n] y
⏳ Indexing... ✓ Done (23 files, 47 chunks)

🤖 Based on your notes, embeddings are...

You: What about transformers?

🤖 Your notes mention...

You: /quit
```

### Single-Shot Mode

```bash
# Ask with @folder context
mdcli ask "@my-notes What are embeddings?"
mdcli ask "@docs Explain the API" --provider anthropic
```

### Other Commands

```bash
# Configuration
mdcli config set-backend <url>
mdcli config set-webhook <url>

# Manual upload (optional, @folder handles this)
mdcli upload ./folder/ --namespace="custom"

# Raw vector search
mdcli query "search term" --top-k=10

# Status & Jobs
mdcli status
mdcli jobs list
mdcli jobs status <job-id>
```

### Inside Chat Session (/commands)

| Command | Description |
|---------|-------------|
| `/help` | Show commands |
| `/quit` | Exit chat |
| `/index @folder` | Force re-index |
| `/provider anthropic` | Switch LLM |
| `/status` | Show context |
| `/clear` | Clear screen |

---

## API Endpoints (Final)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/health/detailed` | Detailed health with dependencies |
| POST | `/api/upload` | Upload and index markdown file |
| POST | `/api/query` | Vector similarity search |
| GET | `/api/search` | Simple search (query params) |
| POST | `/api/ask` | RAG: retrieve context + LLM answer |
| GET | `/api/providers` | List available LLM providers |
| GET | `/api/conversation/{thread_id}` | Get conversation history |
| DELETE | `/api/conversation/{thread_id}` | Clear conversation history |
| GET | `/api/status` | Index statistics |
| GET | `/api/jobs` | List processing jobs |
| GET | `/api/jobs/{id}` | Get job status |

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- OpenAI API key
- Pinecone API key
- (Optional) Anthropic API key
- (Optional) Ollama installed locally

### Quick Start

```bash
# 1. Clone and setup
cd llm-md-cli
cp .env.example .env
# Edit .env with your API keys

# 2. Build and start
make build
make up

# 3. Install CLI
./install-cli.sh
export PATH="$HOME/.mdcli:$PATH"

# 4. Configure CLI
mdcli config set-backend http://localhost:8000

# 5. Test it out
mdcli upload ./your-notes.md
mdcli query "your search"
mdcli ask "your question"
```

---

## How to Use These Plans with Claude Code

Each phase file is designed to be used as instructions for Claude Code:

1. Open the phase file (e.g., `phase-1-setup-upload.md`)
2. Copy the relevant task section
3. Paste to Claude Code with: "Implement Task 1.1 from this plan"
4. Review and iterate

**Example prompts:**

```
Implement Task 1.3: Markdown Parser & Chunker from the Phase 1 plan.
Follow the function signatures exactly.
```

```
Create the Celery configuration as described in Task 4.2.
Use the exact settings from the plan.
```

```
Implement the complete backend/llm/ module from Phase 3,
including all three providers (OpenAI, Anthropic, Ollama).
```

---

## Future Enhancements (Post-MVP)

These are NOT included in the current plan but could be added later:

- [ ] JWT authentication
- [ ] User registration/login
- [ ] Rate limiting
- [ ] Multi-file batch uploads
- [ ] Scheduled re-indexing
- [ ] Admin dashboard
- [ ] Cloud deployment (AWS/GCP)
- [ ] Comprehensive test suite
- [ ] CI/CD pipeline

---

## @folder Reference System

The key UX feature is the **@folder reference** (inspired by Claude Code):

```
@my-notes What did I learn?
     │
     └─► Resolves to ~/Documents/my-notes
         │
         ├─► If not indexed: prompts to index
         │
         └─► If indexed: uses cached namespace
```

**Index Cache:** `~/.mdcli/index_cache.json` tracks:
- Which folders are indexed
- File hashes (to detect changes)
- Namespace mappings

**Re-indexing:** Only happens when user explicitly selects the folder again via `/index @folder`

---

## File Manifest

```
plans/
├── README.md                      # This file - overview
│
├── ── Implementation Details (split for smaller context) ──
├── models.md                      # Pydantic models (requests/responses/jobs)
├── cli-modules.md                 # CLI: API client, config, cache, resolver
├── backend-core.md                # Parser, embedder, Pinecone, config
├── backend-api.md                 # FastAPI routes and endpoints
├── backend-services.md            # RAG service, job store, webhook
├── langgraph.md                   # LangGraph workflow, nodes, runner
│
├── ── Phase Plans ──
├── phase-1-setup-upload.md        # Project setup, upload, indexing
├── phase-2-query-search.md        # Vector search functionality
├── phase-2.5-interactive-chat.md  # Interactive chat, @folder refs, TUI
├── phase-3-chat-rag.md            # Multi-provider LLM, RAG
├── phase-4-async-webhooks.md      # Celery, Redis, webhooks
└── phase-5-docker-deployment.md   # Docker, deployment
```

---

## How to Generate Code

**For any LLM (GPT-4, Claude, etc.):**

The implementation details have been split into smaller, focused files to avoid context window issues:

| File | Contents | ~Lines |
|------|----------|--------|
| [models.md](./models.md) | Pydantic models (requests, responses, jobs) | ~180 |
| [cli-modules.md](./cli-modules.md) | API client, config, index cache, folder resolver | ~450 |
| [backend-core.md](./backend-core.md) | Markdown parser, embedder, Pinecone, logging | ~400 |
| [backend-api.md](./backend-api.md) | FastAPI routes, endpoints, main.py | ~350 |
| [backend-services.md](./backend-services.md) | RAG service, job store, webhook, Celery tasks | ~400 |
| [langgraph.md](./langgraph.md) | LangGraph state, nodes, workflow, runner | ~450 |

### Recommended Order

1. **Start with `models.md`** — defines all data structures
2. **Then `backend-core.md`** — core infrastructure (parser, embedder, Pinecone)
3. **Then `backend-services.md`** — business logic (RAG, jobs, webhooks)
4. **Then `langgraph.md`** — LangGraph workflow with conversation memory
5. **Then `backend-api.md`** — API endpoints that use all the above
6. **Then `cli-modules.md`** — CLI components that call the API

### Example Prompts

```
Using models.md, create all the Pydantic models in backend/models/.
Follow the code exactly as specified.
```

```
Using backend-core.md, implement the markdown chunker in
backend/parser/markdown.py with the exact function signatures.
```

```
Using langgraph.md, create the complete backend/graph/ module
including state.py, nodes.py, workflow.py, and runner.py.
```

### Phase Files

Use the phase files for:
- Project structure scaffolding
- Docker/deployment config
- TUI layout (textual library)
- CLI commands (typer)
