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
