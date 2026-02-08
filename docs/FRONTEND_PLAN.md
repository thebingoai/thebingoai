# Frontend Development Plan - LLM-MD-CLI Web UI

**Version:** 1.0  
**Date:** 2026-02-08  
**Branch:** feature/frontend-plan  
**Target:** React + TypeScript SPA with FastAPI backend

---

## Executive Summary

Build a modern web interface for llm-md-cli that provides an intuitive way to:
- Upload and manage markdown documents
- Search and query indexed content
- Chat with documents using RAG
- Monitor system status and jobs
- Manage namespaces and settings

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Framework** | React 18 + TypeScript | Type safety, component ecosystem |
| **Build Tool** | Vite | Fast dev server, optimized builds |
| **Styling** | Tailwind CSS + Headless UI | Rapid UI development, accessibility |
| **State Management** | Zustand + TanStack Query | Simple state, server state caching |
| **Routing** | React Router v6 | SPA navigation |
| **Icons** | Lucide React | Consistent icon set |
| **Charts** | Recharts | Status visualization |
| **WebSocket** | Native WebSocket API | Real-time streaming responses |
| **HTTP Client** | Axios | Request/response interceptors |

---

## Feature Matrix

### Core Features

| Feature | Priority | Status | Backend API |
|---------|----------|--------|-------------|
| Document Upload | P0 | Planned | POST /api/upload |
| Folder Upload | P0 | Planned | POST /api/upload (batch) |
| Vector Search | P0 | Planned | POST /api/query |
| RAG Chat | P0 | Planned | POST /api/ask |
| Streaming Responses | P0 | Planned | WebSocket/SSE |
| Namespace Management | P1 | Planned | GET /api/status |
| Job Monitoring | P1 | Planned | GET /api/jobs |
| Conversation History | P1 | Planned | GET /api/conversation/{id} |
| Provider Switching | P1 | Planned | GET /api/providers |
| Settings Management | P2 | Planned | TBD |
| User Authentication | P2 | Planned | TBD |
| Dashboard Analytics | P2 | Planned | TBD |

---

## Page Structure

### 1. Layout Components

```
src/
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx          # Navigation sidebar
│   │   ├── Header.tsx           # Top header with user/actions
│   │   ├── Layout.tsx           # Main layout wrapper
│   │   └── MobileNav.tsx        # Mobile navigation drawer
│   └── ui/                      # Reusable UI components
├── pages/
│   └── ...
└── App.tsx
```

**Layout Features:**
- Collapsible sidebar (responsive)
- Breadcrumb navigation
- Dark/light theme toggle
- User profile dropdown
- Global search bar
- Notification center

---

### 2. Dashboard Page (`/`)

**Purpose:** Overview and quick actions

**Sections:**
1. **Stats Cards** (4-column grid)
   - Total documents indexed
   - Total vectors in Pinecone
   - Active namespaces
   - Recent queries count

2. **Quick Actions** (2-column grid)
   - Upload document (drag-drop zone)
   - Start new chat
   - Search documents
   - View recent jobs

3. **Recent Activity** (table/list)
   - Recent uploads with status
   - Recent queries
   - Active conversations

4. **System Status** (sidebar widget)
   - Backend health
   - Pinecone connection
   - Redis status
   - LLM providers available

**Backend APIs:**
- GET /health/detailed
- GET /api/status
- GET /api/jobs?limit=5

---

### 3. Documents Page (`/documents`)

**Purpose:** Manage uploaded documents and namespaces

**Layout:**
- Left sidebar: Namespace tree
- Main area: Document list/grid

**Features:**
1. **Namespace Tree**
   - Hierarchical folder structure
   - Expand/collapse folders
   - Context menu (rename, delete, refresh)
   - Search/filter namespaces

2. **Document List**
   - Table view: filename, namespace, chunks, indexed date, actions
   - Grid view: cards with preview
   - Sort by: date, name, size
   - Filter by: namespace, date range, tags
   - Bulk actions (delete, re-index, export)

3. **Upload Zone**
   - Drag & drop area
   - File type validation (.md, .txt, .pdf)
   - Progress bars for uploads
   - Folder upload support
   - Namespace selection

4. **Document Preview Modal**
   - Markdown rendering
   - Chunk visualization
   - Metadata display

**Backend APIs:**
- GET /api/status (for namespaces)
- POST /api/upload
- GET /api/jobs (for upload progress)

---

### 4. Search Page (`/search`)

**Purpose:** Vector similarity search across documents

**Layout:**
- Search bar (prominent, centered)
- Filters sidebar (collapsible)
- Results area

**Features:**
1. **Search Interface**
   - Large search input with autocomplete
   - Namespace selector (multi-select)
   - Similarity threshold slider
   - Top-K result count selector

2. **Results Display**
   - List view with relevance scores
   - Highlight matching text
   - Source document links
   - Filter chips (remove filters)

3. **Result Card**
   - Content preview (expandable)
   - Source file path
   - Chunk index
   - Similarity score (0-1)
   - "View in document" link
   - "Ask about this" button

4. **Search History**
   - Recent searches
   - Saved searches

**Backend APIs:**
- POST /api/query
- GET /api/search

---

### 5. Chat Page (`/chat`)

**Purpose:** RAG-powered conversational interface

**Layout:**
- Full-screen chat interface (Claude/ChatGPT style)
- Sidebar: Conversation history
- Main: Chat thread

**Features:**
1. **Conversation Sidebar**
   - List of past conversations
   - Search conversations
   - New chat button
   - Delete conversation
   - Rename conversation

2. **Chat Interface**
   - Message bubbles (user/assistant)
   - Streaming text animation
   - Code syntax highlighting
   - Markdown rendering
   - Copy message button
   - Regenerate response

3. **Context Panel** (collapsible)
   - Selected namespace(s)
   - Retrieved chunks for current query
   - Toggle chunk visibility in response

4. **Input Area**
   - Multi-line text input
   - @mention namespace selector
   - Provider/model selector
   - Temperature slider (advanced)
   - Send button with loading state

5. **Message Actions**
   - Copy to clipboard
   - Thumbs up/down feedback
   - View sources (chunks used)
   - Edit message (re-query)

**Backend APIs:**
- POST /api/ask (streaming)
- GET /api/conversation/{id}
- DELETE /api/conversation/{id}
- GET /api/providers

**WebSocket:** Real-time streaming for chat responses

---

### 6. Jobs Page (`/jobs`)

**Purpose:** Monitor background tasks

**Layout:**
- Table view of all jobs
- Filter/sort controls

**Features:**
1. **Jobs Table**
   - Columns: ID, Type, Status, Progress, Created, Completed, Actions
   - Status badges: pending, processing, completed, failed
   - Progress bars for active jobs
   - Retry failed jobs
   - Cancel pending jobs

2. **Job Details Modal**
   - Full job information
   - Logs/output
   - Error messages (if failed)
   - Related documents

3. **Auto-refresh**
   - Poll for updates every 5 seconds
   - Visual indicator when new jobs arrive

**Backend APIs:**
- GET /api/jobs
- GET /api/jobs/{id}

---

### 7. Settings Page (`/settings`)

**Purpose:** Configure application settings

**Sections:**
1. **Backend Connection**
   - Backend URL input
   - Connection test button
   - Default namespace selector

2. **LLM Providers**
   - List configured providers
   - Add/edit provider API keys
   - Default provider selection
   - Model preferences

3. **Embedding Settings**
   - Model selection (if configurable)
   - Chunk size configuration
   - Overlap percentage

4. **Appearance**
   - Theme selector (light/dark/system)
   - Font size
   - Compact/comfortable density

5. **Data Management**
   - Clear local cache
   - Export data
   - Import data

6. **About**
   - Version info
   - Backend version
   - Links to documentation

**Backend APIs:**
- GET /api/providers
- GET /health/detailed

---

## Component Library

### Reusable Components

| Component | Props | Description |
|-----------|-------|-------------|
| `Button` | variant, size, loading, disabled | Action buttons |
| `Input` | type, placeholder, error, icon | Form inputs |
| `Select` | options, value, onChange, multi | Dropdown selector |
| `Dialog` | open, onClose, title, actions | Modal dialogs |
| `Toast` | message, type, duration | Notifications |
| `ProgressBar` | value, max, animated | Progress indicator |
| `FileUpload` | accept, multiple, onUpload | File dropzone |
| `SearchInput` | value, onSearch, loading | Search with debounce |
| `MarkdownViewer` | content, highlights | Render markdown |
| `CodeBlock` | code, language | Syntax highlighted code |
| `NamespaceTree` | data, onSelect, actions | Folder tree view |
| `ChatMessage` | role, content, sources | Chat bubble |
| `StreamingText` | text, speed | Typewriter effect |
| `StatusBadge` | status, pulse | Health/status indicator |
| `DataTable` | columns, data, pagination | Sortable table |

---

## State Management

### Zustand Stores

```typescript
// stores/authStore.ts
interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
}

// stores/chatStore.ts
interface ChatState {
  conversations: Conversation[];
  currentConversation: Conversation | null;
  messages: Message[];
  isStreaming: boolean;
  sendMessage: (content: string) => void;
  loadConversation: (id: string) => void;
}

// stores/documentStore.ts
interface DocumentState {
  namespaces: Namespace[];
  documents: Document[];
  selectedNamespace: string | null;
  uploadProgress: UploadProgress[];
  refreshNamespaces: () => Promise<void>;
}

// stores/settingsStore.ts
interface SettingsState {
  backendUrl: string;
  theme: 'light' | 'dark' | 'system';
  defaultProvider: string;
  updateSettings: (settings: Partial<Settings>) => void;
}
```

### TanStack Query (Server State)

```typescript
// hooks/useNamespaces.ts
export const useNamespaces = () => {
  return useQuery({
    queryKey: ['namespaces'],
    queryFn: fetchNamespaces,
    refetchInterval: 30000, // 30s
  });
};

// hooks/useChat.ts
export const useChat = (conversationId?: string) => {
  return useMutation({
    mutationFn: sendChatMessage,
    onSuccess: (data) => {
      // Handle streaming response
    },
  });
};
```

---

## API Integration

### API Client Setup

```typescript
// lib/api.ts
import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 120000,
});

// Request interceptor - add auth headers
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle auth error
    }
    return Promise.reject(error);
  }
);
```

### Streaming Response Handler

```typescript
// lib/streaming.ts
export async function* streamChat(message: string, namespace: string) {
  const response = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: message, namespace, stream: true }),
  });

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    // Parse SSE data
    const text = new TextDecoder().decode(value);
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        yield JSON.parse(line.slice(6));
      }
    }
  }
}
```

---

## Routes Definition

```typescript
// App.tsx
const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'documents', element: <DocumentsPage /> },
      { path: 'documents/:namespace', element: <DocumentsPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'chat/:conversationId', element: <ChatPage /> },
      { path: 'jobs', element: <JobsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
  { path: '/login', element: <LoginPage /> },
]);
```

---

## Development Phases

### Phase 1: Foundation (Week 1)
- [ ] Project setup (Vite + React + TypeScript)
- [ ] Tailwind + component library setup
- [ ] API client configuration
- [ ] Routing setup
- [ ] Layout components (Sidebar, Header)

### Phase 2: Core Features (Week 2-3)
- [ ] Dashboard page
- [ ] Documents page (upload, list)
- [ ] Search page
- [ ] Basic chat interface

### Phase 3: Advanced Features (Week 4)
- [ ] Streaming chat responses
- [ ] Conversation history
- [ ] Jobs monitoring
- [ ] Settings page

### Phase 4: Polish (Week 5)
- [ ] Dark mode
- [ ] Mobile responsiveness
- [ ] Error handling
- [ ] Loading states
- [ ] Animations

### Phase 5: Optional (Week 6)
- [ ] Authentication
- [ ] Dashboard analytics
- [ ] PWA support

---

## File Structure

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── Layout.tsx
│   │   │   └── MobileNav.tsx
│   │   ├── ui/              # Reusable UI components
│   │   └── chat/
│   │       ├── ChatMessage.tsx
│   │       ├── ChatInput.tsx
│   │       └── StreamingText.tsx
│   ├── pages/
│   │   ├── DashboardPage.tsx
│   │   ├── DocumentsPage.tsx
│   │   ├── SearchPage.tsx
│   │   ├── ChatPage.tsx
│   │   ├── JobsPage.tsx
│   │   └── SettingsPage.tsx
│   ├── hooks/
│   │   ├── useNamespaces.ts
│   │   ├── useDocuments.ts
│   │   ├── useChat.ts
│   │   └── useJobs.ts
│   ├── stores/
│   │   ├── authStore.ts
│   │   ├── chatStore.ts
│   │   ├── documentStore.ts
│   │   └── settingsStore.ts
│   ├── lib/
│   │   ├── api.ts
│   │   ├── streaming.ts
│   │   └── utils.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## Environment Variables

```bash
# .env
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_NAME=LLM-MD-CLI
VITE_ENABLE_AUTH=false
```

---

## Backend Requirements

For full frontend functionality, backend needs:

1. **CORS enabled** for frontend origin
2. **WebSocket support** for streaming (or SSE)
3. **Authentication endpoints** (if auth enabled)
4. **Pagination** for large result sets
5. **File upload progress** (currently async jobs)

---

## Success Criteria

- [ ] All P0 features implemented
- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Dark/light theme
- [ ] < 3s initial load time
- [ ] Smooth streaming chat experience
- [ ] Comprehensive error handling
- [ ] Accessibility (WCAG 2.1 AA)

---

## Next Steps

1. Create `frontend/` directory
2. Initialize Vite project
3. Install dependencies
4. Set up API client
5. Build layout components
6. Implement Dashboard page first

---

*This plan is a living document. Update as requirements change.*
