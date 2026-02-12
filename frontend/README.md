# LLM-MD-CLI Frontend

Nuxt 4 + Pinia frontend for the LLM-MD-CLI RAG system.

## Tech Stack

- **Framework**: Nuxt 4 (Vue 3)
- **State Management**: Pinia with persistedstate
- **Styling**: Tailwind CSS 3
- **UI Components**: Headless UI + Lucide Icons
- **Dark Mode**: @nuxtjs/color-mode
- **Markdown**: markdown-it + shiki
- **Charts**: vue-chartjs
- **Notifications**: vue-sonner

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### Build for Production

```bash
npm run build
npm run preview
```

### Type Check

```bash
npm run type-check
```

## Environment Variables

Create a `.env` file:

```env
NUXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Project Structure

```
frontend/
├── app.vue                 # Root component
├── nuxt.config.ts         # Nuxt configuration
├── tailwind.config.ts     # Tailwind configuration
├── types/index.ts         # TypeScript types
├── utils/                 # Utility functions
├── stores/                # Pinia stores (settings, chat, search)
├── composables/           # Vue composables (API, data fetching)
├── components/
│   ├── layout/           # Layout components (sidebar, header)
│   ├── ui/               # Reusable UI components (13 components)
│   ├── dashboard/        # Dashboard-specific components
│   ├── documents/        # Documents page components
│   ├── search/           # Search page components
│   ├── chat/             # Chat page components (with SSE streaming)
│   ├── jobs/             # Jobs page components
│   └── settings/         # Settings page components
├── pages/
│   ├── index.vue         # Dashboard
│   ├── documents/        # Documents management
│   ├── search.vue        # Vector search
│   ├── chat/             # RAG chat with streaming
│   ├── jobs.vue          # Job monitoring
│   └── settings.vue      # Settings
└── plugins/              # Nuxt plugins

## Features

### Dashboard
- System status overview
- Stats cards (documents, vectors, namespaces)
- Quick actions
- Recent activity feed

### Documents
- Namespace browser
- File upload with progress tracking
- Drag-and-drop support
- Namespace-specific views

### Search
- Full-text vector search
- Filter by namespace, top-k, min score
- Search history
- Score-based result ranking

### Chat (RAG)
- Streaming responses with SSE
- Conversation management
- Message history
- Source citations
- Provider/model selection
- Temperature control

### Jobs
- Real-time job monitoring
- Status tracking (pending, processing, completed, failed)
- Auto-refresh for active jobs
- Detailed job information

### Settings
- Backend connection configuration
- Theme selection (light/dark/system)
- Font size and density controls
- Default namespace/provider settings

## Key Composables

- `useApi()` - API client wrapper
- `useStreaming()` - SSE streaming for chat
- `useUpload()` - File upload with progress
- `useChat()` - Chat orchestration with abort support
- `useSearch()` - Search with history tracking
- `useStatus()`, `useJobs()`, `useProviders()` - Data fetching

## Keyboard Shortcuts

- `Cmd/Ctrl + K` - Go to search
- `Cmd/Ctrl + N` - Start new chat
- `Enter` - Send message (in chat)
- `Shift + Enter` - New line (in chat)

## Dark Mode

Dark mode is handled by `@nuxtjs/color-mode`:
- Auto-detects system preference
- Persists user selection
- CSS class-based (`class="dark"`)

## SSE Streaming

The chat uses Server-Sent Events for streaming responses:
- Progressive token rendering
- Real-time source updates
- Abort support
- Error handling

Event types:
- `sources` - Source documents
- `token` - Text token
- `thread_id` - Conversation ID
- `done` - Stream complete
- `error` - Error occurred

## API Integration

All API calls go through `composables/useApi.ts`:
- Automatic baseURL from settings/config
- Error handling with user-friendly messages
- Upload progress tracking via XHR
- Type-safe request/response

## State Persistence

Three Pinia stores with selective persistence:

1. **settings** (fully persisted)
   - Backend URL, connection status
   - Default namespace/provider
   - Theme, font size, density

2. **chat** (partial)
   - Conversations, settings
   - Messages cleared on reload

3. **search** (history only)
   - Search history persisted

## Browser Support

- Modern browsers with ES2020+ support
- SSE/EventSource API required for chat streaming
- Tested on Chrome, Firefox, Safari, Edge
