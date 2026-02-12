# Enterprise Adaptive BI Agent - MVP Overview

## Product Vision

An AI-powered Business Intelligence agent that connects to enterprise databases, generates SQL queries from natural language, executes them safely in read-only mode, and adapts to user patterns through a memory system. The agent learns from interactions, improving accuracy and efficiency over time.

## Core Capabilities

1. **Natural Language to SQL**: Users ask questions in plain English, agent generates and executes SQL
2. **Multi-Database Support**: Connect to PostgreSQL, MySQL, and other databases with read-only access
3. **Self-Correcting Query Agent**: Uses LangGraph for multi-step reasoning with error recovery
4. **Memory System**: Daily interaction summaries stored in Qdrant for context-aware responses
5. **Token Usage Tracking**: Monitor costs and usage patterns per user
6. **Authentication**: JWT-based auth for multi-user support
7. **Modern UI**: Nuxt 4 frontend with data visualization, SQL display, and memory insights

## Architecture Overview

### Backend (FastAPI)
- **Application Database** (PostgreSQL): Users, database connections, conversations, token usage
- **Auth System**: JWT tokens, bcrypt password hashing, FastAPI security dependencies
- **Database Connectors**: Factory pattern for multi-database support (Postgres, MySQL)
- **Agent Orchestration**: Orchestrator routes to specialized sub-agents based on intent
  - **Orchestrator**: Main ReAct agent with conversation memory (MemorySaver)
  - **Data Agent**: Stateless SQL query agent with schema discovery tools
  - **RAG Agent**: Wrapper around existing document RAG system
  - **Skills Framework**: Dynamic skill registration (SummarizeSkill, etc.)
  - **Memory Agent**: Stub for Phase 06 (recall conversation history)
- **Chat API**: SSE streaming for real-time responses, conversation threading
- **Memory System**: Daily summary generation via Celery, stored in Qdrant
- **Token Tracking**: Per-user usage monitoring for cost control

### Frontend (Nuxt 4)
- **Auth Pages**: Login, registration with JWT storage
- **Connections Manager**: Add/edit/test database connections
- **Chat Interface**: Natural language query input, data tables, charts, SQL display
- **Memory Dashboard**: View interaction history and agent learning
- **Usage Dashboard**: Token consumption and cost tracking

### Infrastructure (Reuse Existing)
- **Redis**: Job queue (Celery broker), results backend, cache
- **Qdrant**: Self-hosted vector storage for RAG + memory system (Docker container)
- **Celery**: Async tasks for memory generation and heavy processing
- **Docker Compose**: Orchestrates all services

## Key Design Decisions

### 1. Qdrant Collections with Tenant Isolation
- Two collections by purpose: `documents` (RAG embeddings) and `memories` (interaction summaries)
- Tenant isolation via indexed `tenant_id` payload field within each collection
- Self-hosted via Docker — no cloud vendor dependency
- Pinecone namespaces mapped internally: `"memory:user-*"` → `memories` collection, others → `documents` collection

### 2. Read-Only Database Connections
- All customer database connections are read-only by default
- Connection string validation enforces read-only mode
- Security first: Prevents accidental data modification

### 3. Orchestrator-Based Agent Architecture
- **Single-channel communication**: Nuxt frontend → REST/SSE → Orchestrator
- **Orchestrator routes to sub-agents**: Data Agent, RAG Agent, Skills (via tool calls, not subgraphs)
- **Closure-based context**: AgentContext passed via closures for thread-safety (no globals)
- **Data Agent**: Stateless ReAct agent with schema discovery tools (list_tables, get_table_schema, search_tables, execute_query)
- **RAG Agent**: Wraps existing langgraph/runner.py for document queries
- **Skills Framework**: Dynamic registration (BaseSkill, SkillRegistry)
- **Conversation memory**: Orchestrator has MemorySaver checkpointer (thread_id-based)

### 4. Daily Memory Generation
- Celery task runs daily per user
- Summarizes conversations using LLM
- Stores in Qdrant `memories` collection for retrieval during future queries
- Includes: common questions, schema patterns, error corrections, preferences

### 5. Token Tracking Granularity
- Per-user, per-operation tracking (chat, memory generation, query)
- Stored in PostgreSQL for analytics
- Enables cost attribution and usage limits

### 6. Orchestrator Architecture Flow
```
User Request → Nuxt Frontend → REST API (+ SSE) → Auth (JWT)
                                                     ↓
                                          AgentContext (user_id, connections, thread_id)
                                                     ↓
                                    Orchestrator (ReAct + MemorySaver)
                                    ├── data_agent    → Data Agent (closure-based tools)
                                    │                    ├── list_tables
                                    │                    ├── get_table_schema
                                    │                    ├── search_tables
                                    │                    └── execute_query
                                    ├── rag_agent     → RAG Agent (wraps langgraph/runner.py)
                                    ├── recall_memory  → Memory Agent (Phase 06 stub)
                                    └── skills        → SkillRegistry
                                                         └── summarize_text, ...
```

**Key differences from OpenClaw**:
- **Single channel**: Nuxt frontend only (not 13+ messaging channels)
- **No WebSocket gateway**: Direct REST/SSE communication
- **Closure-based context**: Thread-safe without globals
- **Sub-agents as tools**: Orchestrator invokes via tool calls (not subgraphs)

## Infrastructure Reuse

### Existing Components (No Changes)
- Qdrant vector store (3072 dimensions, text-embedding-3-large, cosine distance)
- Redis (3 DBs: cache, broker, results)
- Celery worker architecture
- Upload processing (markdown files)
- OpenAI embeddings
- LangGraph framework
- Docker Compose setup

### New Components
- PostgreSQL for app database (new container)
- Alembic for migrations
- SQLAlchemy ORM models
- Database connector factory
- JWT auth system
- Memory generation Celery task
- Frontend authentication flow

## Migration Strategy

### Phase 1-4: Backend Foundation
Build core backend without disrupting existing RAG functionality:
- Add PostgreSQL + models (Phase 1)
- Add auth (Phase 2)
- Add database connectors (Phase 3)
- Build agent orchestration (Phase 4)
  - Orchestrator with conversation memory
  - Data Agent (stateless, closure-based tools)
  - RAG Agent wrapper
  - Skills Framework

### Phase 5-7: Integration & Tracking
Wire up the complete backend:
- Integrate auth with chat API (Phase 5)
- Add memory system (Phase 6)
- Add token tracking (Phase 7)

### Phase 8: Cleanup
- Update config for new features
- Remove dead code
- Clean up requirements
- Update documentation

### Phase 9-11: Frontend
Build UI progressively:
- Auth + connections UI (Phase 9)
- Chat UI with data viz (Phase 10)
- Memory + usage dashboards (Phase 11)

## Success Criteria

### MVP Completion Checklist
- [ ] User can register and login
- [ ] User can add database connection (Postgres or MySQL)
- [ ] User can ask natural language questions
- [ ] Agent generates and executes SQL queries
- [ ] Results displayed as tables and charts
- [ ] Agent self-corrects failed queries
- [ ] Daily memory summaries generated
- [ ] Memory influences future query generation
- [ ] Token usage tracked and displayed
- [ ] All existing RAG functionality works unchanged

### Performance Targets
- Query generation: < 3s for simple queries
- Query execution: Depends on database (out of scope)
- Memory generation: < 5 min per user per day
- UI responsiveness: < 100ms for user interactions

### Security Requirements
- All passwords bcrypt hashed
- JWTs expire after 24 hours
- Database connections are read-only
- SQL injection prevention via parameterized queries
- CORS configured for frontend domain only

## Non-Goals for MVP

- Multi-tenancy (single-user per deployment for MVP)
- Query result caching
- Real-time collaboration
- Advanced chart customization
- Export to CSV/Excel
- Scheduled queries
- Alert system for anomalies
- Role-based access control (RBAC)

These can be added in future iterations after MVP validation.
