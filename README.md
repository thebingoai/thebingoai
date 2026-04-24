# Bingo

[![License: BSUL](https://img.shields.io/badge/License-Bingo_Sustainable_Use-blue.svg)](./LICENSE)

A BI platform with AI-powered dashboards, real-time chat, and multi-database connectivity. Built with FastAPI, Nuxt 4, and LangGraph.

## Overview

Bingo provides:
- **AI-powered dashboards** with drag-and-drop widgets (GridStack)
- **Real-time WebSocket chat** with RAG (Retrieval-Augmented Generation)
- **Multi-provider LLM support** (OpenAI, Anthropic, Ollama)
- **Database connectors** for PostgreSQL and MySQL
- **AI agent system** with orchestrator, data, dashboard, RAG, and monitor agents
- **Bingo SSO authentication**
- **Background job processing** via Celery with scheduled tasks
- **Memory system** for persistent conversation context

## Architecture

```
┌──────────────┐    HTTP / WebSocket    ┌─────────────────┐
│ Nuxt Frontend│ ◄─────────────────────► │  FastAPI Backend │
│  (Port 3000) │                        │   (Port 8000)    │
└──────────────┘                        └────────┬─────────┘
                                                 │
                  ┌──────────┬───────────┬───────┼───────────┐
                  │          │           │       │           │
                  ▼          ▼           ▼       ▼           ▼
            ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
            │PostgreSQL│ │ Qdrant │ │ Redis  │ │ Celery │ │  Agent   │
            │(Primary  │ │(Vector │ │(Cache +│ │(Worker │ │  Worker  │
            │  DB)     │ │ Store) │ │ Queue) │ │+ Beat) │ │          │
            └──────────┘ └────────┘ └────────┘ └────────┘ └──────────┘
```

**Services** (via Docker Compose):
- **PostgreSQL 15** — primary relational database
- **Qdrant** — self-hosted vector database for embeddings
- **Redis** — cache (DB 0), Celery broker (DB 1), Celery results (DB 2), agent mesh (DB 4)
- **Celery Worker** — background task processing (uploads, jobs)
- **Celery Beat** — scheduled task execution
- **Agent Worker** — dedicated worker for AI agent tasks (data, dashboard, RAG, custom queues)

## Getting Started

### Prerequisites

- Docker and Docker Compose
- `.env` file with API keys

### Quick Start

```bash
# Clone the repository
git clone https://github.com/thebingoai/thebingoai.git bingo && cd bingo

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys (at minimum: OPENAI_API_KEY, DB_ENCRYPTION_KEY)

# Start all services
./start.sh
```

`start.sh` brings up all services via Docker Compose and waits for the backend health check.

**Access points:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Useful Commands

```bash
# View logs
docker compose -f docker/local/docker-compose.yml logs -f [service]

# Restart a service
docker compose -f docker/local/docker-compose.yml restart [service]

# Stop all services
docker compose -f docker/local/docker-compose.yml down

# Rebuild after code changes
docker compose -f docker/local/docker-compose.yml up --build -d
```

## Project Structure

```
bingo/
├── backend/
│   ├── agents/          # AI agent system (orchestrator, data, dashboard, RAG, monitor)
│   ├── api/             # API route handlers
│   ├── auth/            # Auth provider system (Supabase, base, factory)
│   ├── connectors/      # Database connectors (PostgreSQL, MySQL)
│   ├── database/        # SQLAlchemy models and database setup
│   ├── embedder/        # Embedding generation (OpenAI)
│   ├── langgraph/       # LangGraph RAG implementation
│   ├── llm/             # LLM provider factory (OpenAI, Anthropic, Ollama)
│   ├── memory/          # Persistent memory system
│   ├── models/          # Pydantic request/response models
│   ├── schemas/         # Database schema definitions
│   ├── security/        # Security utilities
│   ├── services/        # Core services (indexing, jobs, retrieval)
│   ├── tasks/           # Celery background tasks
│   ├── tests/           # Backend tests
│   └── vectordb/        # Vector database abstraction
├── frontend/            # Nuxt 4 application
│   ├── components/      # Vue components
│   ├── composables/     # Shared composables (useApi, etc.)
│   ├── pages/           # File-based routing (dashboard, chat, auth, settings)
│   └── stores/          # Pinia stores (auth, etc.)
├── alembic/             # Database migrations
├── docker/
│   ├── backend/         # Backend Dockerfile
│   ├── frontend/        # Frontend Dockerfile
│   └── local/           # Local dev docker-compose.yml
├── docs/                # Documentation
├── plugins/             # Plugin system
├── start.sh             # Local development startup script
└── requirements.txt     # Python dependencies
```

## API Endpoints

### Authentication
- `POST /api/auth/...` — Bingo SSO authentication flows (login, signup, verify, reset password)

### Database Connections
- `/api/connections/...` — Manage database connections (PostgreSQL, MySQL)
- `/api/sql/...` — Direct SQL query execution

### Chat
- `/api/chat/...` — WebSocket-powered chat with RAG orchestrator
- `/api/chat-files/...` — File uploads for chat context (CSV, PDF, text)

### Dashboards & Widgets
- `/api/dashboards/...` — Dashboard CRUD
- `/api/widget-data/...` — Widget data refresh
- `/api/dashboard-schedules/...` — Scheduled dashboard updates

### AI Agents
- `/api/agents/...` — Custom agent registry
- `/api/agent-sessions/...` — Agent mesh sessions
- `/api/skills/...` — User skill management

### Memory & Context
- `/api/memory/...` — Persistent memory system

### Document Indexing
- `POST /api/upload` — Upload and index markdown files
- `POST /api/query` — Query indexed documents with natural language
- `GET /api/search` — Search indexed documents

### System
- `GET /health` — Health check
- `GET /api/status` — Detailed system status
- `GET /api/info` — Application info
- `GET /api/jobs` / `GET /api/jobs/{job_id}` — Background job tracking
- `/api/usage/...` — Usage tracking
- `/api/heartbeat-jobs/...` — Heartbeat job management

## Environment Variables

Copy `.env.example` to `.env` and configure:

### Required
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (for embeddings and LLM) |
| `DB_ENCRYPTION_KEY` | Fernet key for database password encryption |

### Optional — LLM Providers
| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OLLAMA_BASE_URL` | Ollama endpoint (default: `http://localhost:11434`) |
| `DEFAULT_LLM_PROVIDER` | `openai` / `anthropic` / `ollama` (default: `openai`) |

### Optional — Bingo SSO
| Variable | Description |
|----------|-------------|
| `SSO_BASE_URL` | SSO service URL (default: `https://sso.thebingo.ai`) |
| `SSO_PUBLISHABLE_KEY` | App name (community) or `pk_*` publishable key (enterprise) |
| `SSO_SECRET_KEY` | Backend `sk_*` secret key (enterprise only; adds `X-API-Key` header) |
| `SSO_TOKEN_CACHE_TTL` | Token cache TTL in seconds (default: `300`) |
| `SSO_WEBHOOK_SECRET` | Optional webhook signature verification secret |
| `SSO_REDIS_URL` | Redis URL for token cache (default: `redis://localhost:6379/3`) |

### Optional — Storage & Infrastructure
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `QDRANT_URL` | Qdrant connection string |

See `.env.example` for the full list of configuration options.

## Requirements

- Docker and Docker Compose
- At minimum: `OPENAI_API_KEY` and `DB_ENCRYPTION_KEY` in `.env`
- Optional: `ANTHROPIC_API_KEY` for Anthropic provider, Ollama running locally for local LLM

## Development Status

- [x] FastAPI backend with PostgreSQL
- [x] AI-powered dashboards with drag-and-drop widgets
- [x] Real-time WebSocket chat with RAG
- [x] Multi-provider LLM support (OpenAI, Anthropic, Ollama)
- [x] Database connectors (PostgreSQL, MySQL)
- [x] AI agent system (orchestrator, data, dashboard, RAG, monitor)
- [x] Bingo SSO authentication
- [x] Background job processing with Celery
- [x] Scheduled tasks with Celery Beat
- [x] Memory system for persistent context
- [x] Document indexing and vector search (Qdrant)
- [x] Nuxt 4 frontend
- [x] Docker Compose local development setup
- [x] Database migrations with Alembic
- [x] Usage tracking

## Contributing

Issues and PRs welcome. See [LICENSE](./LICENSE) for terms.

## License

Bingo Community is source-available under the [Bingo Sustainable Use License](./LICENSE) — a fair-code license. You are free to self-host, modify, and use Bingo internally. Offering Bingo as a hosted service to third parties, or removing license and copyright notices, is not permitted. For commercial hosting rights, contact The Bingo AI.
