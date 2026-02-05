# Phase 2: Query & Search

## Overview
Implement vector search functionality in the backend and add query commands to the CLI.

## Duration: Week 2

---

## Task 2.1: Pinecone Query Function

### Update `backend/vectordb/pinecone.py`

**Add query functionality:**

```python
async def query_vectors(
    query_embedding: list[float],
    namespace: str = "default",
    top_k: int = 5,
    filter: dict | None = None,
    include_metadata: bool = True
) -> list[dict]:
    """
    Query Pinecone for similar vectors.

    Args:
        query_embedding: The query vector (3072 dimensions)
        namespace: Namespace to search in
        top_k: Number of results to return
        filter: Metadata filter (e.g., {"source": "notes.md"})
        include_metadata: Whether to return metadata with results

    Returns:
        [
            {
                "id": "file.md#chunk-3",
                "score": 0.89,
                "metadata": {
                    "source": "file.md",
                    "chunk_index": 3,
                    "text": "The actual text content...",
                    "created_at": "2024-01-15"
                }
            },
            ...
        ]
    """
    pass

async def list_namespaces() -> list[str]:
    """List all namespaces in the index."""
    pass

async def get_index_stats() -> dict:
    """Get index statistics (vector count, namespaces, etc.)."""
    pass
```

---

## Task 2.2: Query API Endpoint

### Create `backend/api/query.py`

**Endpoint:** `POST /api/query`

**Request body:**
```json
{
    "query": "What are the key points about embeddings?",
    "namespace": "default",
    "top_k": 5,
    "filter": {
        "source": "notes.md"
    }
}
```

**Response:**
```json
{
    "query": "What are the key points about embeddings?",
    "results": [
        {
            "id": "notes.md#chunk-2",
            "score": 0.92,
            "source": "notes.md",
            "chunk_index": 2,
            "text": "Embeddings are dense vector representations...",
            "created_at": "2024-01-15"
        }
    ],
    "namespace": "default",
    "total_results": 5
}
```

**Processing flow:**
1. Receive query text
2. Generate embedding for query using OpenAI
3. Query Pinecone with embedding
4. Format and return results

---

## Task 2.3: Search API Endpoint (Simplified)

### Add to `backend/api/query.py`

**Endpoint:** `GET /api/search`

A simpler endpoint for basic searches.

**Query parameters:**
- `q` (required): Search query string
- `namespace` (optional): Namespace to search, default "default"
- `limit` (optional): Max results, default 5

**Example:** `GET /api/search?q=embeddings&namespace=personal&limit=10`

**Response:** Same format as POST /api/query

---

## Task 2.4: Stats/Status Endpoint

### Create `backend/api/status.py`

**Endpoint:** `GET /api/status`

**Response:**
```json
{
    "status": "healthy",
    "index": {
        "name": "llm-md-index",
        "total_vectors": 1523,
        "dimension": 3072,
        "namespaces": {
            "default": {"vector_count": 500},
            "personal": {"vector_count": 1023}
        }
    },
    "embedding_model": "text-embedding-3-large"
}
```

---

## Task 2.5: Update API Router

### Update `backend/api/routes.py`

```python
from fastapi import APIRouter
from backend.api import upload, query, status

router = APIRouter()

# Upload routes
router.post("/upload")(upload.upload_file)

# Query routes
router.post("/query")(query.query)
router.get("/search")(query.search)

# Status routes
router.get("/status")(status.get_status)
```

---

## Task 2.6: CLI Query Command

### Create `cli/cmd/query.py`

**Commands:**

```bash
# Basic query - returns matching chunks
mdcli query "What did I learn about LLMs?"

# With options
mdcli query "embeddings" --namespace="work" --top-k=10

# Filter by source file
mdcli query "machine learning" --source="notes.md"

# Output formats
mdcli query "LLMs" --format=json
mdcli query "LLMs" --format=table
mdcli query "LLMs" --format=compact  # default
```

**Output format (compact - default):**

```
Found 5 results for "What did I learn about LLMs?"

[1] notes.md (chunk 3) - Score: 0.92
    Embeddings are dense vector representations that capture semantic
    meaning. They're the foundation of modern LLM applications...

[2] research.md (chunk 7) - Score: 0.87
    Large Language Models have revolutionized NLP by using transformer
    architectures with billions of parameters...

[3] ...
```

**Implementation requirements:**
- Use rich for formatted output
- Support JSON output for scripting
- Show scores rounded to 2 decimal places
- Truncate long text with "..." (configurable with --full)
- Handle errors gracefully (no results, connection issues)

---

## Task 2.7: CLI Status Command

### Create `cli/cmd/status.py`

**Commands:**

```bash
# Check backend health
mdcli status

# Show detailed index info
mdcli status --verbose
```

**Output:**

```
✓ Backend: Connected (http://localhost:8000)
✓ Index: llm-md-index
  Total vectors: 1,523
  Namespaces: default (500), personal (1,023)
```

---

## Task 2.8: Update CLI Main

### Update `cli/main.py`

```python
import typer
from cli.cmd import config, upload, query, status

app = typer.Typer(
    name="mdcli",
    help="CLI for indexing and querying markdown files with LLMs"
)

app.add_typer(config.app, name="config")
app.command()(upload.upload)
app.command()(query.query)
app.command()(status.status)

if __name__ == "__main__":
    app()
```

---

## Task 2.9: Error Handling

### Create `backend/api/errors.py`

**Custom exceptions:**

```python
from fastapi import HTTPException

class VectorDBError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=503, detail=f"Vector DB error: {detail}")

class EmbeddingError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=502, detail=f"Embedding error: {detail}")

class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)
```

### Create `cli/errors.py`

```python
import typer
from rich.console import Console

console = Console()

def handle_api_error(response):
    """Handle API error responses gracefully."""
    if response.status_code == 503:
        console.print("[red]Error:[/red] Vector database unavailable")
    elif response.status_code == 502:
        console.print("[red]Error:[/red] Embedding service unavailable")
    elif response.status_code == 404:
        console.print("[yellow]No results found[/yellow]")
    else:
        console.print(f"[red]Error {response.status_code}:[/red] {response.text}")
    raise typer.Exit(1)
```

---

## Verification Checklist

After implementation, verify:

- [ ] POST /api/query returns relevant results
- [ ] GET /api/search works with query params
- [ ] GET /api/status returns index statistics
- [ ] CLI `mdcli query` displays results nicely
- [ ] CLI `mdcli query --format=json` outputs valid JSON
- [ ] CLI `mdcli status` shows connection and index info
- [ ] Error handling works (test with backend down)
- [ ] Namespace filtering works correctly
- [ ] Top-k parameter limits results appropriately

---

## Testing Commands

```bash
# Test query endpoint
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "embeddings", "top_k": 3}'

# Test search endpoint
curl "http://localhost:8000/api/search?q=embeddings&limit=3"

# Test status endpoint
curl http://localhost:8000/api/status

# Test CLI commands
python -m cli.main query "embeddings"
python -m cli.main query "LLMs" --namespace=personal --top-k=10
python -m cli.main status --verbose
```
