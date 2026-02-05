# Phase 1: Project Setup & Upload/Index

## Overview
Set up the project structure, create the FastAPI backend with upload endpoint, implement markdown chunking, OpenAI embeddings, and Pinecone integration.

## Duration: Week 1

---

## Task 1.1: Project Scaffolding

### Create directory structure
```
llm-md-cli/
├── cli/
│   ├── __init__.py
│   ├── main.py
│   └── cmd/
│       ├── __init__.py
│       ├── config.py
│       └── upload.py
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── upload.py
│   ├── embedder/
│   │   ├── __init__.py
│   │   └── openai.py
│   ├── parser/
│   │   ├── __init__.py
│   │   └── markdown.py
│   └── vectordb/
│       ├── __init__.py
│       └── pinecone.py
├── requirements.txt
├── cli-requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### Files to create

**backend/requirements.txt**
```
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6
openai==1.12.0
pinecone-client==3.0.0
tiktoken==0.5.2
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0
httpx==0.26.0
```

**cli/requirements.txt**
```
typer==0.9.0
httpx==0.26.0
rich==13.7.0
pyyaml==6.0.1
```

**.env.example**
```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=llm-md-index
PINECONE_ENVIRONMENT=us-east-1
```

---

## Task 1.2: Backend Configuration

### Create `backend/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str = "llm-md-index"
    pinecone_environment: str = "us-east-1"

    # Chunking settings
    chunk_size: int = 512  # tokens
    chunk_overlap: float = 0.2  # 20% overlap

    # Embedding settings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Task 1.3: Markdown Parser & Chunker

### Create `backend/parser/markdown.py`

**Requirements:**
- Accept raw markdown text
- Split into chunks of ~512 tokens with 20% overlap
- Use tiktoken for accurate token counting
- Preserve markdown structure where possible (don't split mid-paragraph)
- Return list of chunks with metadata (index, char_start, char_end)

**Function signatures:**
```python
def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using tiktoken."""
    pass

def chunk_markdown(
    text: str,
    chunk_size: int = 512,
    overlap: float = 0.2
) -> list[dict]:
    """
    Split markdown into chunks.

    Returns:
        [
            {
                "index": 0,
                "text": "chunk content...",
                "token_count": 487,
                "char_start": 0,
                "char_end": 1523
            },
            ...
        ]
    """
    pass
```

**Chunking strategy:**
1. Split by double newlines (paragraphs)
2. If paragraph > chunk_size, split by sentences
3. Combine small paragraphs until approaching chunk_size
4. Apply overlap by including last N tokens from previous chunk

---

## Task 1.4: OpenAI Embeddings

### Create `backend/embedder/openai.py`

**Requirements:**
- Use text-embedding-3-large model (3072 dimensions)
- Support batch embedding (multiple texts at once)
- Handle rate limits with exponential backoff
- Return embeddings as list of floats

**Function signatures:**
```python
async def embed_text(text: str) -> list[float]:
    """Embed a single text string."""
    pass

async def embed_batch(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Embed multiple texts efficiently."""
    pass
```

---

## Task 1.5: Pinecone Integration

### Create `backend/vectordb/pinecone.py`

**Requirements:**
- Initialize Pinecone client on startup
- Create index if it doesn't exist (3072 dimensions, cosine metric)
- Upsert vectors with metadata
- Support namespaces for multi-tenancy

**Function signatures:**
```python
def init_pinecone() -> None:
    """Initialize Pinecone client and ensure index exists."""
    pass

async def upsert_vectors(
    vectors: list[dict],
    namespace: str = "default"
) -> dict:
    """
    Upsert vectors to Pinecone.

    Args:
        vectors: [
            {
                "id": "file.md#chunk-0",
                "values": [...3072 floats...],
                "metadata": {
                    "source": "file.md",
                    "chunk_index": 0,
                    "text": "raw text...",
                    "created_at": "2024-01-15"
                }
            }
        ]
        namespace: User/project namespace

    Returns:
        {"upserted_count": 5}
    """
    pass
```

---

## Task 1.6: Upload API Endpoint

### Create `backend/api/upload.py`

**Endpoint:** `POST /api/upload`

**Request:**
- Multipart form data
- Field: `file` (markdown file)
- Field: `namespace` (optional, string)
- Field: `tags` (optional, comma-separated)

**Response:**
```json
{
    "status": "success",
    "file_name": "notes.md",
    "chunks_created": 5,
    "vectors_upserted": 5,
    "namespace": "default"
}
```

**Processing flow:**
1. Receive uploaded file
2. Read and validate (must be .md)
3. Parse and chunk markdown
4. Generate embeddings for all chunks
5. Upsert to Pinecone with metadata
6. Return summary

---

## Task 1.7: FastAPI Application

### Create `backend/main.py`

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.vectordb.pinecone import init_pinecone
from backend.api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Pinecone
    init_pinecone()
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title="LLM-MD Backend",
    version="0.1.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Task 1.8: CLI Upload Command

### Create `cli/cmd/config.py`

**Config file location:** `~/.mdcli/config.yaml`

```yaml
backend_url: http://localhost:8000
# No auth for MVP
```

**Commands:**
```bash
mdcli config set-backend <url>
mdcli config show
```

### Create `cli/cmd/upload.py`

**Commands:**
```bash
mdcli upload <file_or_directory>
mdcli upload ./notes/*.md --namespace="personal"
mdcli upload ./docs/ --recursive --tag="project"
```

**Features:**
- Upload single file or glob pattern
- Recursive directory upload with `--recursive`
- Add tags with `--tag`
- Specify namespace with `--namespace`
- Show progress with rich progress bar
- Display summary on completion

---

## Task 1.9: CLI Main Entry Point

### Create `cli/main.py`

```python
import typer
from cli.cmd import config, upload

app = typer.Typer(
    name="mdcli",
    help="CLI for indexing and querying markdown files with LLMs"
)

app.add_typer(config.app, name="config")
app.command()(upload.upload)

if __name__ == "__main__":
    app()
```

---

## Verification Checklist

After implementation, verify:

- [ ] Backend starts without errors: `uvicorn backend.main:app`
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] Can upload a test .md file via curl
- [ ] Chunks appear in Pinecone dashboard
- [ ] CLI config commands work
- [ ] CLI upload command successfully uploads files
- [ ] Multiple files can be uploaded with glob patterns

---

## Environment Setup Instructions

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Install CLI dependencies
pip install -r cli-requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run backend
uvicorn backend.main:app --reload

# Test CLI (in another terminal)
python -m cli.main config show
python -m cli.main upload ./test.md
```
