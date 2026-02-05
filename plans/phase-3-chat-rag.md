# Phase 3: Chat & RAG with Multi-Provider LLM Support

## Overview
Implement RAG (Retrieval-Augmented Generation) with chat capabilities. Support multiple LLM providers: OpenAI, Anthropic, and Ollama (local models).

## Duration: Week 3

---

## Task 3.1: LLM Provider Abstraction

### Create `backend/llm/__init__.py`

**Provider interface with exports:**

```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Send messages and get response."""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens."""
        pass

# Import providers for convenient access
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.llm.factory import get_provider

__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "get_provider"
]
```

---

## Task 3.2: OpenAI Provider

### Create `backend/llm/openai_provider.py`

```python
from backend.llm import LLMProvider
from openai import AsyncOpenAI

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def chat(self, messages, temperature=0.7, max_tokens=1000) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def chat_stream(self, messages, temperature=0.7, max_tokens=1000):
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

**Supported models:**
- `gpt-4o` (default)
- `gpt-4-turbo`
- `gpt-3.5-turbo`

---

## Task 3.3: Anthropic Provider

### Create `backend/llm/anthropic_provider.py`

**Add to requirements.txt:**
```
anthropic==0.18.0
```

```python
from backend.llm import LLMProvider
from anthropic import AsyncAnthropic

class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def chat(self, messages, temperature=0.7, max_tokens=1000) -> str:
        # Convert OpenAI message format to Anthropic format
        system_msg = ""
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        response = await self.client.messages.create(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.content[0].text

    async def chat_stream(self, messages, temperature=0.7, max_tokens=1000):
        system_msg = ""
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        async with self.client.messages.stream(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            temperature=temperature,
            max_tokens=max_tokens
        ) as stream:
            async for text in stream.text_stream:
                yield text
```

**Supported models:**
- `claude-sonnet-4-20250514` (default)
- `claude-3-5-haiku-20241022`
- `claude-3-opus-20240229`

---

## Task 3.4: Ollama Provider (Local Models)

### Create `backend/llm/ollama_provider.py`

```python
from backend.llm import LLMProvider
import httpx

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model

    async def chat(self, messages, temperature=0.7, max_tokens=1000) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def chat_stream(self, messages, temperature=0.7, max_tokens=1000):
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=120.0
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
```

**Supported models (examples):**
- `llama3` (default)
- `mistral`
- `codellama`
- Any model available in user's Ollama installation

---

## Task 3.5: Provider Factory

### Create `backend/llm/factory.py`

```python
from backend.llm import LLMProvider
from backend.llm.openai_provider import OpenAIProvider
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.ollama_provider import OllamaProvider
from backend.config import settings

def get_provider(
    provider: str = "openai",
    model: str | None = None
) -> LLMProvider:
    """
    Factory function to get LLM provider.

    Args:
        provider: "openai", "anthropic", or "ollama"
        model: Optional model override

    Returns:
        LLMProvider instance
    """
    if provider == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=model or "gpt-4o"
        )
    elif provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=model or "claude-sonnet-4-20250514"
        )
    elif provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=model or "llama3"
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

---

## Task 3.6: Update Configuration

### Update `backend/config.py`

```python
class Settings(BaseSettings):
    # Existing settings...

    # LLM Provider settings
    anthropic_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # Default LLM settings
    default_llm_provider: str = "openai"
    default_llm_model: str | None = None

    class Config:
        env_file = ".env"
```

### Update `.env.example`

```
# Existing keys...
OPENAI_API_KEY=sk-...

# Additional LLM providers (optional)
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434

# Default LLM settings
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o
```

---

## Task 3.7: RAG Service

### Create `backend/services/rag.py`

```python
from backend.vectordb.pinecone import query_vectors
from backend.embedder.openai import embed_text
from backend.llm.factory import get_provider

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.
Use the context to answer the user's question. If the context doesn't contain relevant information,
say so and provide what help you can.

Context:
{context}
"""

async def ask_with_context(
    question: str,
    namespace: str = "default",
    top_k: int = 5,
    provider: str = "openai",
    model: str | None = None,
    temperature: float = 0.7,
    stream: bool = False
):
    """
    RAG: Retrieve relevant context and generate answer.

    Args:
        question: User's question
        namespace: Namespace to search
        top_k: Number of context chunks to retrieve
        provider: LLM provider to use
        model: Optional model override
        temperature: Generation temperature
        stream: Whether to stream response

    Returns:
        If stream=False: {"answer": "...", "sources": [...]}
        If stream=True: AsyncGenerator yielding tokens
    """
    # 1. Embed the question
    query_embedding = await embed_text(question)

    # 2. Retrieve relevant chunks
    results = await query_vectors(
        query_embedding=query_embedding,
        namespace=namespace,
        top_k=top_k
    )

    # 3. Build context from results
    context_parts = []
    sources = []
    for r in results:
        context_parts.append(f"[From {r['metadata']['source']}]:\n{r['metadata']['text']}")
        sources.append({
            "source": r["metadata"]["source"],
            "chunk_index": r["metadata"]["chunk_index"],
            "score": r["score"]
        })

    context = "\n\n---\n\n".join(context_parts)

    # 4. Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": question}
    ]

    # 5. Get LLM response
    llm = get_provider(provider, model)

    if stream:
        async def stream_with_sources():
            async for token in llm.chat_stream(messages, temperature=temperature):
                yield token
        return stream_with_sources(), sources
    else:
        answer = await llm.chat(messages, temperature=temperature)
        return {"answer": answer, "sources": sources}
```

---

## Task 3.8: Ask/Chat API Endpoint

### Create `backend/api/chat.py`

**Endpoint:** `POST /api/ask`

**Request body:**
```json
{
    "question": "What are the main points about embeddings?",
    "namespace": "default",
    "top_k": 5,
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.7,
    "stream": false
}
```

**Response (non-streaming):**
```json
{
    "answer": "Based on your notes, the main points about embeddings are...",
    "sources": [
        {
            "source": "notes.md",
            "chunk_index": 2,
            "score": 0.92
        }
    ],
    "provider": "openai",
    "model": "gpt-4o"
}
```

**Streaming response:**
- Content-Type: `text/event-stream`
- Server-Sent Events format
- Final event includes sources

```
data: Based on
data: your notes
data: , the main
...
data: [DONE]
data: {"sources": [...]}
```

---

## Task 3.9: List Providers Endpoint

### Add to `backend/api/chat.py`

**Endpoint:** `GET /api/providers`

**Response:**
```json
{
    "providers": [
        {
            "name": "openai",
            "available": true,
            "models": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        },
        {
            "name": "anthropic",
            "available": true,
            "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]
        },
        {
            "name": "ollama",
            "available": false,
            "models": [],
            "error": "Connection refused"
        }
    ],
    "default": {
        "provider": "openai",
        "model": "gpt-4o"
    }
}
```

---

## Task 3.10: CLI Ask Command

### Create `cli/cmd/ask.py`

**Commands:**

```bash
# Basic ask with RAG
mdcli ask "What did I learn about embeddings?"

# Specify provider
mdcli ask "Summarize my LLM notes" --provider=anthropic
mdcli ask "Explain transformers" --provider=ollama --model=mistral

# Control context retrieval
mdcli ask "What's important?" --namespace=work --top-k=10

# Streaming output
mdcli ask "Give me a summary" --stream

# Show sources
mdcli ask "What are embeddings?" --show-sources
```

**Output (default):**

```
Based on your notes, embeddings are dense vector representations that capture
semantic meaning of text. They enable similarity search by placing related
concepts close together in vector space. Your notes mention that OpenAI's
text-embedding-3-large model produces 3072-dimensional vectors...

Sources:
  • notes.md (chunk 2) - relevance: 92%
  • research.md (chunk 7) - relevance: 87%
```

**Implementation requirements:**
- Stream responses with real-time display using rich
- Show typing indicator while waiting
- Format sources nicely at the end
- Support --json flag for programmatic use

---

## Task 3.11: CLI Providers Command

### Add to `cli/cmd/ask.py`

```bash
# List available providers
mdcli providers

# Output:
# Available LLM Providers:
# ✓ openai (gpt-4o, gpt-4-turbo, gpt-3.5-turbo)
# ✓ anthropic (claude-sonnet-4-20250514, claude-3-5-haiku-20241022)
# ✗ ollama - not available (connection refused)
#
# Default: openai/gpt-4o
```

---

## Task 3.12: Update API Router

### Update `backend/api/routes.py`

```python
from backend.api import upload, query, status, chat

router = APIRouter()

# Existing routes...
router.post("/upload")(upload.upload_file)
router.post("/query")(query.query)
router.get("/search")(query.search)
router.get("/status")(status.get_status)

# Chat/RAG routes
router.post("/ask")(chat.ask)
router.get("/providers")(chat.list_providers)
```

---

## Verification Checklist

After implementation, verify:

- [ ] OpenAI provider works: `mdcli ask "test" --provider=openai`
- [ ] Anthropic provider works: `mdcli ask "test" --provider=anthropic`
- [ ] Ollama provider works (if installed): `mdcli ask "test" --provider=ollama`
- [ ] Streaming works in CLI
- [ ] Sources are returned correctly
- [ ] Provider list endpoint shows availability
- [ ] Error handling for unavailable providers
- [ ] Context is correctly retrieved and included
- [ ] Temperature and top_k parameters work

---

## Testing Commands

```bash
# Test ask endpoint
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are embeddings?", "provider": "openai"}'

# Test with Anthropic
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are embeddings?", "provider": "anthropic"}'

# Test streaming
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are embeddings?", "stream": true}'

# Test providers endpoint
curl http://localhost:8000/api/providers

# Test CLI
python -m cli.main ask "What are embeddings?"
python -m cli.main ask "Summarize" --provider=anthropic --stream
python -m cli.main providers
```
