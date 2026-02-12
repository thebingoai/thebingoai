# Feature Test Plan - LLM-MD-CLI

## Pre-Refactor Feature Baseline

### Backend Features
- [ ] Health check endpoint (/health)
- [ ] Detailed health check (/health/detailed)
- [ ] File upload endpoint (/api/upload)
- [ ] Vector query endpoint (/api/query)
- [ ] Search endpoint (/api/search)
- [ ] RAG chat endpoint (/api/ask) - streaming
- [ ] RAG chat endpoint (/api/ask) - non-streaming
- [ ] List providers endpoint (/api/providers)
- [ ] Get conversation history (/api/conversation/{id})
- [ ] Delete conversation (/api/conversation/{id})
- [ ] Index status endpoint (/api/status)
- [ ] List jobs endpoint (/api/jobs)
- [ ] Get job status endpoint (/api/jobs/{id})

### CLI Features
- [ ] Upload single file (mdcli upload file)
- [ ] Upload folder (mdcli upload folder)
- [ ] Batch upload (mdcli upload batch)
- [ ] Query vector store (mdcli query)
- [ ] Chat single-shot (mdcli chat ask)
- [ ] Interactive TUI chat (mdcli chat)
- [ ] Index list (mdcli index list)
- [ ] Index stats (mdcli index stats)
- [ ] Index delete (mdcli index delete)
- [ ] Index clear (mdcli index clear)
- [ ] Index refresh (mdcli index refresh)
- [ ] Status check (mdcli status)
- [ ] Configure backend URL (mdcli configure)
- [ ] Show config (mdcli config-show)

### Core Functionality
- [ ] @folder reference resolution
- [ ] Folder indexing with hash tracking
- [ ] Changed file detection
- [ ] Cache persistence
- [ ] Multi-provider LLM support (OpenAI, Anthropic, Ollama)
- [ ] Conversation thread persistence
- [ ] Streaming response handling
- [ ] Error handling with user-friendly messages
