# LLM-MD-CLI

CLI tool for indexing and querying markdown files using LLMs.

## Overview

This project provides:
- A FastAPI backend for uploading and indexing markdown files
- Pinecone vector storage for semantic search
- OpenAI embeddings for text vectorization
- A CLI tool (`mdcli`) for easy file upload

## Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Running the Backend

```bash
uvicorn backend.main:app --reload
```

The backend will be available at `http://localhost:8000`.

## Installing the CLI

```bash
# Install CLI in development mode
pip install -e .

# Or use CLI directly without installation
python -m cli.main --help
```

## CLI Usage

```bash
# Show current configuration
mdcli config show

# Set backend URL
mdcli config set-backend <url>

# Upload a single file
mdcli upload ./notes.md

# Upload with namespace
mdcli upload ./notes.md --namespace="personal"

# Upload multiple files with glob
mdcli upload ./docs/*.md --tag="project"

# Upload directory recursively
mdcli upload ./docs/ --recursive --tag="project"
```

## API Endpoints

- `POST /api/upload` - Upload and index a markdown file
- `GET /health` - Health check endpoint

## Configuration

The CLI stores configuration in `~/.mdcli/config.yaml`:

```yaml
backend_url: http://localhost:8000
```

## Requirements

- Python 3.10+
- OpenAI API key
- Pinecone API key
