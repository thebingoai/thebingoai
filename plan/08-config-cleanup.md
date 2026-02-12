# Phase 08: Config Cleanup and Backend Finalization

## Objective

Update configuration for new features, remove dead/unused code, clean up requirements.txt, update Docker Compose, and finalize backend documentation.

## Prerequisites

- Phases 01-07 complete (all backend features implemented)

## Files to Modify

### Configuration
- `backend/config.py` - Review and update all settings
- `.env.example` - Add new environment variables
- `docker-compose.yml` - Ensure all services configured correctly

### Dependencies
- `requirements.txt` - Remove unused, add missing, organize by category

### Documentation
- `README.md` - Update with new features and setup instructions
- `CLAUDE.md` - Update with new architecture details

## Files to Delete

Identify and remove:
- Dead code from old RAG-only implementation
- Unused helper modules
- Deprecated API endpoints
- Old test files for removed features

## Implementation Details

### 1. Review and Update Config (backend/config.py)

Ensure all new settings are present:

```python
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Database
    database_url: str = Field(...)

    # JWT Authentication
    jwt_secret_key: str = Field(...)
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration_minutes: int = Field(default=1440)

    # LLM Providers
    openai_api_key: str = Field(...)
    anthropic_api_key: str = Field(default=None)
    ollama_base_url: str = Field(default="http://localhost:11434")
    default_llm_provider: str = Field(default="openai")
    default_llm_model: str = Field(default="gpt-4-turbo")

    # Embeddings
    embedding_model: str = Field(default="text-embedding-3-large")
    embedding_dimensions: int = Field(default=3072)

    # Qdrant
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_grpc_port: int = Field(default=6334)
    qdrant_api_key: Optional[str] = Field(default=None)
    qdrant_use_grpc: bool = Field(default=True)
    qdrant_documents_collection: str = Field(default="documents")
    qdrant_memories_collection: str = Field(default="memories")
    qdrant_upsert_batch_size: int = Field(default=100)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # Chunking (for RAG - keep existing)
    chunk_size: int = Field(default=512)
    chunk_overlap: float = Field(default=0.2)

    # Logging
    log_level: str = Field(default="INFO")

    # CORS (for frontend)
    cors_origins: List[str] = Field(default=["http://localhost:3000"])

    class Config:
        env_file = ".env"
```

### 2. Update .env.example

```bash
# Database
DATABASE_URL=postgresql://llm_user:llm_password@localhost:5432/llm_cli

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_EXPIRATION_MINUTES=1440

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4-turbo

# Embeddings
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=3072

# Qdrant (self-hosted)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334
QDRANT_API_KEY=                          # Optional: only if auth enabled
QDRANT_DOCUMENTS_COLLECTION=documents
QDRANT_MEMORIES_COLLECTION=memories

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Chunking
CHUNK_SIZE=512
CHUNK_OVERLAP=0.2

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 3. Review Docker Compose (docker-compose.yml)

Ensure all services are configured:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: llm-cli-postgres
    environment:
      POSTGRES_DB: llm_cli
      POSTGRES_USER: llm_user
      POSTGRES_PASSWORD: llm_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U llm_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: llm-cli-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: .
    container_name: llm-cli-backend
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://llm_user:llm_password@postgres:5432/llm_cli
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app/backend
      - ./uploads:/app/uploads

  celery-worker:
    build: .
    container_name: llm-cli-celery-worker
    command: celery -A backend.tasks.celery_app worker --loglevel=info
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://llm_user:llm_password@postgres:5432/llm_cli
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend:/app/backend

  celery-beat:
    build: .
    container_name: llm-cli-celery-beat
    command: celery -A backend.tasks.celery_app beat --loglevel=info
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql://llm_user:llm_password@postgres:5432/llm_cli
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    depends_on:
      - redis
      - postgres
    volumes:
      - ./backend:/app/backend

volumes:
  postgres_data:
  redis_data:
```

### 4. Organize Requirements (requirements.txt)

```txt
# Core Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.25
alembic==1.13.1
psycopg2-binary==2.9.9

# Database Connectors
PyMySQL==1.1.0

# Authentication
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0

# LLM & AI
openai==1.10.0
anthropic==0.9.0
langchain-core==0.1.20
langgraph==0.0.25

# Vector Database
qdrant-client>=1.12.0,<2.0.0

# Embeddings
tiktoken==0.5.2

# Async & Background Tasks
celery==5.3.6
redis==5.0.1

# Utilities
python-multipart==0.0.6
python-dotenv==1.0.0

# Markdown Processing (for existing RAG)
markdown-it-py==3.0.0

# Cryptography
cryptography==41.0.7

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

### 5. Update README.md

Add sections for:
- New features (query agent, auth, memory)
- Quick start guide
- API documentation overview
- Architecture diagram
- Contributing guidelines

### 6. Update CLAUDE.md

Add sections documenting:
- Authentication system
- Database connector architecture
- Query agent workflow
- Memory system architecture
- Token tracking implementation
- Frontend-backend integration points

### 7. Code Cleanup Tasks

Run through codebase and identify:

**Files to potentially delete:**
- Old upload processing code (if superseded)
- Unused helper modules
- Dead test files
- Temporary debug scripts

**Code to refactor:**
- Duplicate schema definitions
- Inconsistent error handling patterns
- Magic numbers (convert to constants)
- Hardcoded values (move to config)

**Documentation to add:**
- Docstrings for all public functions
- API endpoint descriptions
- Error response formats
- Example requests/responses

## Testing & Verification

### 1. Environment Validation

Create script: `backend/scripts/validate_env.py`

```python
#!/usr/bin/env python3
"""Validate environment configuration."""

from backend.config import settings
import sys

def validate_config():
    """Validate all required config values are set."""
    errors = []

    # Required settings
    if settings.database_url == "":
        errors.append("DATABASE_URL not set")

    if settings.jwt_secret_key == "your-secret-key-change-in-production":
        errors.append("JWT_SECRET_KEY still using default value (security risk!)")

    if not settings.openai_api_key:
        errors.append("OPENAI_API_KEY not set")

    # Qdrant is self-hosted, no API key required by default
    # Only validate if qdrant_api_key is explicitly expected

    if errors:
        print("❌ Configuration validation failed:\n")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ Configuration validation passed")

if __name__ == "__main__":
    validate_config()
```

Run before deployment:
```bash
python backend/scripts/validate_env.py
```

### 2. Service Health Checks

Verify all services start correctly:

```bash
docker-compose up -d
docker-compose ps  # All should be "Up (healthy)"
docker-compose logs backend | grep "Application startup complete"
docker-compose logs celery-worker | grep "ready"
```

### 3. API Smoke Tests

```bash
# Health check
curl http://localhost:8000/health

# API docs
curl http://localhost:8000/docs

# Test auth flow
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

### 4. Database Migration Check

```bash
alembic current  # Should show latest revision
alembic history  # Should show all migrations
```

## MCP Browser Testing

N/A - Backend cleanup only

## Code Review Checklist

- [ ] All environment variables documented in .env.example
- [ ] No hardcoded secrets in code
- [ ] All dependencies pinned to specific versions
- [ ] Docker Compose services have health checks
- [ ] README.md updated with new features
- [ ] CLAUDE.md updated with architecture changes
- [ ] Dead code removed
- [ ] Unused imports removed
- [ ] All public functions have docstrings
- [ ] Config validation script works
- [ ] All services start without errors

## Done Criteria

1. Config file includes all new settings
2. .env.example updated and documented
3. Docker Compose configured correctly
4. Requirements.txt organized and complete
5. README.md updated
6. CLAUDE.md updated
7. Dead code removed
8. Config validation script passes
9. All services start successfully
10. API smoke tests pass
11. Database migrations up to date

## Rollback Plan

If cleanup breaks something:
1. Git revert specific changes
2. Restore previous requirements.txt
3. Restore previous docker-compose.yml
4. Rollback config changes

Keep backup of working versions before major refactors.
