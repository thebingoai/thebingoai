# Phase 5: Docker & Deployment

## Overview
Containerize the application with Docker and set up Docker Compose for local/self-hosted deployment.

## Duration: Week 4 (Part 2)

---

## Task 5.1: Backend Dockerfile

### Create `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Default command (can be overridden)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Task 5.2: CLI Dockerfile

### Create `cli/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY cli-requirements.txt .
RUN pip install --no-cache-dir -r cli-requirements.txt

# Copy CLI code
COPY cli/ ./cli/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Create config directory
RUN mkdir -p /home/appuser/.mdcli

ENTRYPOINT ["python", "-m", "cli.main"]
```

---

## Task 5.3: Docker Compose Configuration

### Create `docker-compose.yml`

```yaml
version: "3.8"

services:
  # Redis for Celery broker/backend
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # FastAPI Backend
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - PINECONE_INDEX_NAME=${PINECONE_INDEX_NAME:-llm-md-index}
      - PINECONE_ENVIRONMENT=${PINECONE_ENVIRONMENT:-us-east-1}
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://host.docker.internal:11434}
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Celery Worker
  celery-worker:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: celery -A backend.celery_app worker --loglevel=info --concurrency=2
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - PINECONE_INDEX_NAME=${PINECONE_INDEX_NAME:-llm-md-index}
      - PINECONE_ENVIRONMENT=${PINECONE_ENVIRONMENT:-us-east-1}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
    restart: unless-stopped

  # Optional: Flower for Celery monitoring
  flower:
    build:
      context: .
      dockerfile: backend/Dockerfile
    command: celery -A backend.celery_app flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - celery-worker
    profiles:
      - monitoring

volumes:
  redis_data:
```

---

## Task 5.4: Environment Configuration

### Create `.env.example` (updated)

```bash
# Required: OpenAI API key for embeddings and chat
OPENAI_API_KEY=sk-...

# Required: Pinecone configuration
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=llm-md-index
PINECONE_ENVIRONMENT=us-east-1

# Optional: Additional LLM providers
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Optional: Override defaults
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o

# Async processing thresholds
ASYNC_FILE_SIZE_THRESHOLD=100000
ASYNC_CHUNK_COUNT_THRESHOLD=20
```

### Create `.env.docker`

```bash
# Docker-specific overrides (if needed)
REDIS_URL=redis://redis:6379/0
```

---

## Task 5.5: Docker Ignore Files

### Create `.dockerignore`

```
# Git
.git
.gitignore

# Python
__pycache__
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.pytest_cache/
.coverage
htmlcov/

# Environment
.env
.env.local
.env.*.local

# Documentation
docs/
*.md
!README.md

# Plans (development only)
plans/

# Local development
*.log
*.tmp
```

---

## Task 5.6: Makefile for Common Operations

### Create `Makefile`

```makefile
.PHONY: help build up down logs shell test clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make build      - Build Docker images"
	@echo "  make up         - Start all services"
	@echo "  make up-mon     - Start all services with monitoring"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - View logs"
	@echo "  make shell      - Open shell in backend container"
	@echo "  make test       - Run tests (future)"
	@echo "  make clean      - Remove containers and volumes"

# Build images
build:
	docker compose build

# Start services
up:
	docker compose up -d

# Start with monitoring (Flower)
up-mon:
	docker compose --profile monitoring up -d

# Stop services
down:
	docker compose down

# View logs
logs:
	docker compose logs -f

# Logs for specific service
logs-backend:
	docker compose logs -f backend

logs-worker:
	docker compose logs -f celery-worker

# Shell into backend
shell:
	docker compose exec backend /bin/bash

# Clean up
clean:
	docker compose down -v --remove-orphans
	docker image prune -f

# Development: run backend locally (outside Docker)
dev-backend:
	uvicorn backend.main:app --reload

# Development: run worker locally
dev-worker:
	celery -A backend.celery_app worker --loglevel=info

# Health check
health:
	curl -s http://localhost:8000/health | jq .
```

---

## Task 5.7: CLI Installation Script

### Create `install-cli.sh`

```bash
#!/bin/bash

# Install CLI tool globally
set -e

echo "Installing mdcli..."

# Check Python version
python3 --version || { echo "Python 3 required"; exit 1; }

# Create virtual environment for CLI
CLI_HOME="$HOME/.mdcli"
mkdir -p "$CLI_HOME"

# Install in isolated environment
python3 -m venv "$CLI_HOME/venv"
source "$CLI_HOME/venv/bin/activate"

pip install --upgrade pip
pip install -r cli-requirements.txt

# Create wrapper script
cat > "$CLI_HOME/mdcli" << 'EOF'
#!/bin/bash
source "$HOME/.mdcli/venv/bin/activate"
python -m cli.main "$@"
EOF

chmod +x "$CLI_HOME/mdcli"

# Add to PATH suggestion
echo ""
echo "Installation complete!"
echo ""
echo "Add to your shell profile:"
echo "  export PATH=\"\$HOME/.mdcli:\$PATH\""
echo ""
echo "Then configure:"
echo "  mdcli config set-backend http://localhost:8000"
```

---

## Task 5.8: Production Configuration

### Create `docker-compose.prod.yml`

```yaml
version: "3.8"

# Production overrides
services:
  backend:
    restart: always
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 512M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  celery-worker:
    restart: always
    command: celery -A backend.celery_app worker --loglevel=warning --concurrency=4
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2G
        reservations:
          cpus: "1"
          memory: 1G
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    restart: always
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
```

**Usage:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Task 5.9: Health Check Endpoint Enhancement

### Update `backend/main.py`

```python
from fastapi import FastAPI
from backend.vectordb.pinecone import get_index_stats
import redis
from backend.config import settings

@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy"}

@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check for monitoring."""
    checks = {
        "api": "healthy",
        "redis": "unknown",
        "pinecone": "unknown"
    }

    # Check Redis
    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {str(e)}"

    # Check Pinecone
    try:
        stats = await get_index_stats()
        checks["pinecone"] = "healthy"
        checks["pinecone_vectors"] = stats.get("total_vector_count", 0)
    except Exception as e:
        checks["pinecone"] = f"unhealthy: {str(e)}"

    overall = "healthy" if all(
        v == "healthy" or isinstance(v, int)
        for v in checks.values()
    ) else "degraded"

    return {"status": overall, "checks": checks}
```

---

## Task 5.10: Startup Scripts

### Create `scripts/start.sh`

```bash
#!/bin/bash
set -e

echo "Starting LLM-MD services..."

# Check for .env file
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Copy .env.example to .env and configure your API keys"
    exit 1
fi

# Validate required variables
source .env
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not set"
    exit 1
fi

if [ -z "$PINECONE_API_KEY" ]; then
    echo "Error: PINECONE_API_KEY not set"
    exit 1
fi

# Start services
docker compose up -d

# Wait for health
echo "Waiting for services to be healthy..."
sleep 5

# Check health
curl -s http://localhost:8000/health | grep -q "healthy" && \
    echo "✓ Backend is healthy" || \
    echo "✗ Backend health check failed"

echo ""
echo "Services started!"
echo "  Backend: http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Configure CLI:"
echo "  mdcli config set-backend http://localhost:8000"
```

---

## Directory Structure After Phase 5

```
llm-md-cli/
├── backend/
│   ├── Dockerfile
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── celery_app.py
│   ├── api/
│   ├── embedder/
│   ├── llm/
│   ├── models/
│   ├── parser/
│   ├── services/
│   ├── tasks/
│   └── vectordb/
├── cli/
│   ├── Dockerfile
│   ├── __init__.py
│   ├── main.py
│   └── cmd/
├── scripts/
│   └── start.sh
├── plans/                    # Development plans (not in prod)
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── requirements.txt
├── cli-requirements.txt
├── install-cli.sh
├── .env.example
├── .dockerignore
├── .gitignore
└── README.md
```

---

## Verification Checklist

After implementation, verify:

- [ ] `docker compose build` completes successfully
- [ ] `docker compose up -d` starts all services
- [ ] Backend health check passes: `curl http://localhost:8000/health`
- [ ] Detailed health check works: `curl http://localhost:8000/health/detailed`
- [ ] Redis is accessible from backend
- [ ] Celery worker processes tasks
- [ ] CLI can connect to Dockerized backend
- [ ] Async uploads work end-to-end
- [ ] `docker compose down` cleanly stops services
- [ ] `docker compose --profile monitoring up` starts Flower
- [ ] Flower UI accessible at http://localhost:5555

---

## Quick Start Commands

```bash
# Initial setup
cp .env.example .env
# Edit .env with your API keys

# Build and start
make build
make up

# Check status
make health
docker compose ps

# View logs
make logs

# Stop
make down

# With monitoring
make up-mon
# Flower UI: http://localhost:5555

# CLI setup
./install-cli.sh
export PATH="$HOME/.mdcli:$PATH"
mdcli config set-backend http://localhost:8000

# Test upload
mdcli upload ./test.md
mdcli query "test"
```
