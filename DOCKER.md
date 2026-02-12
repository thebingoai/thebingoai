# Docker Deployment

## Quick Start

### 1. Configure Environment

Edit `.env` and add your API keys:

```bash
OPENAI_API_KEY=sk-your-actual-key-here
PINECONE_API_KEY=your-pinecone-key-here
PINECONE_INDEX_NAME=your-index-name
```

### 2. Start Services

```bash
# Start all services (backend, Redis, Celery worker)
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up --build -d
```

### 3. Verify Deployment

```bash
# Check health
curl http://localhost:8000/health

# Check system status
curl http://localhost:8000/api/status

# View API documentation
open http://localhost:8000/docs
```

## Services

| Service | Container Name | Port | Description |
|---------|----------------|------|-------------|
| Backend | llm-md-backend | 8000:8000 | FastAPI API server |
| Redis | llm-md-redis | 6379:6379 | Job queue & cache |
| Celery | llm-md-celery | - | Background task worker |

## Architecture

```
┌──────────────┐      HTTP/REST     ┌─────────────────┐
│   Frontend   │ ◄─────────────────► │  Docker Backend │
│  (External)  │                     │    (FastAPI)    │
└──────────────┘                     └────────┬────────┘
                                              │
                         ┌────────────────────┼────────────────┐
                         │                    │                │
                         ▼                    ▼                ▼
                   ┌──────────┐         ┌─────────┐     ┌──────────┐
                   │ Pinecone │         │  Redis  │     │  Celery  │
                   │(Vectors) │         │ (Queue) │     │ (Worker) │
                   └──────────┘         └─────────┘     └──────────┘
```

## API Usage

### Upload Documents

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@./test_data/example.md" \
  -F "namespace=test"
```

### Query Documents

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is this document about?",
    "namespace": "test"
  }'
```

### Chat with RAG

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Explain the main concepts",
    "namespace": "test",
    "thread_id": "conversation-123"
  }'
```

## Troubleshooting

### Port already in use
```bash
docker-compose down
# Kill any process on port 8000
lsof -ti:8000 | xargs kill -9
```

### Redis connection failed
```bash
# Check Redis container
docker-compose logs redis

# Restart Redis
docker-compose restart redis
```

### Pinecone errors
- Verify `PINECONE_API_KEY` in `.env`
- Check index exists in Pinecone console
- Ensure index uses correct dimensions (1536 for OpenAI embeddings)

### OpenAI errors
- Verify `OPENAI_API_KEY` in `.env`
- Check API key has credits
- Check rate limits

### Celery worker not processing jobs
```bash
# Check worker logs
docker-compose logs celery-worker

# Restart worker
docker-compose restart celery-worker

# Verify Redis connection
docker-compose exec backend python -c "import redis; r = redis.Redis(host='redis'); print(r.ping())"
```

## Development

For hot-reload during development:
```bash
# Start services
docker-compose up -d

# Backend code changes auto-reload via uvicorn --reload
# To see changes, just edit files and refresh
```

## Production Deployment

For production, consider:
1. Use environment-specific `.env` files
2. Set `DEBUG=false` in `.env`
3. Configure proper CORS origins in `backend/main.py`
4. Use a process manager (e.g., supervisord) for Celery
5. Set up monitoring (e.g., Sentry, Datadog)
6. Use a reverse proxy (e.g., nginx) in front of the FastAPI app
7. Enable HTTPS with proper SSL certificates

## Monitoring

Check job status:
```bash
# List all jobs
curl http://localhost:8000/api/jobs

# Get specific job status
curl http://localhost:8000/api/jobs/{job_id}
```

View system metrics:
```bash
# Get system status
curl http://localhost:8000/api/status
```
