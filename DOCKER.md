# Docker Setup for LLM-MD-CLI

## Quick Start

### 1. Configure Environment

Edit `.env` and add your **OpenAI API Key**:

```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

### 2. Run the Full Setup

```bash
./docker-test.sh
```

This will:
- Build and start all Docker containers (backend, Redis, Celery worker)
- Convert today's news to markdown
- Upload to Pinecone
- Test search and RAG chat

### 3. Manual Control

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up --build -d
```

## Services

| Service | Container Name | Port | Description |
|---------|----------------|------|-------------|
| Backend | llm-md-backend | 8000:8000 | FastAPI API |
| Redis | llm-md-redis | 6379:6379 | Job queue & cache |
| Celery | llm-md-celery | - | Background task worker |

## Testing RAG

After setup, test the RAG system:

```bash
cd cli
pip install -e .

# Configure CLI
mdcli config set-backend http://localhost:8000

# Upload more files
mdcli upload ~/Documents/my-notes.md --namespace=personal

# Query
mdcli query "What happened with Claude?" --namespace=news

# Chat with RAG
mdcli chat "Explain the AI model releases" --namespace=news
```

## Architecture

```
┌─────────────┐      HTTP       ┌─────────────────┐
│   CLI Tool  │ ◄──────────────► │  Docker Backend │
│  (mdcli)    │                  │   (FastAPI)     │
└─────────────┘                  └────────┬────────┘
                                          │
                         ┌────────────────┼────────────────┐
                         │                │                │
                         ▼                ▼                ▼
                   ┌─────────┐     ┌──────────┐    ┌──────────┐
                   │ Pinecone│     │  Redis   │    │  Celery  │
                   │(Vectors)│     │  (Queue) │    │ (Worker) │
                   └─────────┘     └──────────┘    └──────────┘
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

### OpenAI errors
- Verify `OPENAI_API_KEY` in `.env`
- Check API key has credits

## Development

For hot-reload during development:
```bash
docker-compose up -d
# Edit backend code - changes auto-reload
```
