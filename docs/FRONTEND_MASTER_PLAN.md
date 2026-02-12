# Frontend Master Plan — LLM-MD-CLI Web UI

**Version:** 2.0 (Enhanced for Code Generation)
**Target Model:** GLM-4.7
**Date:** 2026-02-08
**Stack:** React 18 + TypeScript + Vite + Tailwind CSS 3 + Zustand + TanStack Query v5

---

## Table of Contents

1. [Project Scaffolding](#1-project-scaffolding)
2. [Dependency Manifest](#2-dependency-manifest)
3. [Configuration Files](#3-configuration-files)
4. [TypeScript Type System](#4-typescript-type-system)
5. [API Client Layer](#5-api-client-layer)
6. [SSE Streaming Client](#6-sse-streaming-client)
7. [State Management Architecture](#7-state-management-architecture)
8. [Routing Configuration](#8-routing-configuration)
9. [Design System & UI/UX Standards](#9-design-system--uiux-standards)
10. [File Structure (Complete)](#10-file-structure-complete)
11. [Implementation Order](#11-implementation-order)
12. [Cross-References](#12-cross-references)

---

## 1. Project Scaffolding

### 1.1 Initialize Project

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
```

### 1.2 Directory Creation

```bash
mkdir -p src/{components/{layout,ui,dashboard,documents,search,chat,jobs,settings},pages,hooks,stores,lib,types,styles,constants}
mkdir -p src/components/ui/{Button,Input,Select,Dialog,Toast,Badge,ProgressBar,Skeleton,FileUpload,DataTable,Tooltip,Dropdown}
mkdir -p public/icons
```

---

## 2. Dependency Manifest

### 2.1 package.json (exact versions)

```json
{
  "name": "llm-md-cli-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.22.0",
    "@tanstack/react-query": "^5.17.0",
    "zustand": "^4.5.0",
    "axios": "^1.6.5",
    "lucide-react": "^0.312.0",
    "recharts": "^2.12.0",
    "@headlessui/react": "^1.7.18",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0",
    "date-fns": "^3.3.0",
    "react-markdown": "^9.0.1",
    "react-syntax-highlighter": "^15.5.0",
    "react-hot-toast": "^2.4.1",
    "react-dropzone": "^14.2.3",
    "framer-motion": "^11.0.3",
    "immer": "^10.0.3"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/react-syntax-highlighter": "^15.5.11",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "eslint": "^8.56.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "postcss": "^8.4.33",
    "tailwindcss": "^3.4.1",
    "typescript": "~5.3.3",
    "vite": "^5.1.0"
  }
}
```

---

## 3. Configuration Files

### 3.1 vite.config.ts

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### 3.2 tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### 3.3 tsconfig.node.json

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

### 3.4 tailwind.config.js

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        surface: {
          DEFAULT: '#ffffff',
          secondary: '#f8fafc',
          tertiary: '#f1f5f9',
          border: '#e2e8f0',
          'dark-DEFAULT': '#0f172a',
          'dark-secondary': '#1e293b',
          'dark-tertiary': '#334155',
          'dark-border': '#475569',
        },
        score: {
          excellent: '#22c55e',
          good: '#3b82f6',
          fair: '#eab308',
          low: '#9ca3af',
        },
        status: {
          healthy: '#22c55e',
          degraded: '#eab308',
          unhealthy: '#ef4444',
          pending: '#9ca3af',
          processing: '#3b82f6',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      spacing: {
        sidebar: '260px',
        'sidebar-collapsed': '72px',
        header: '64px',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
        shimmer: 'shimmer 2s infinite',
        'typing-cursor': 'typingCursor 1s step-end infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseDot: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        typingCursor: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.05), 0 1px 2px -1px rgb(0 0 0 / 0.05)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
        'modal': '0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)',
      },
    },
  },
  plugins: [],
};
```

### 3.5 postcss.config.js

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### 3.6 .env

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_NAME=LLM-MD-CLI
VITE_APP_VERSION=1.0.0
```

### 3.7 index.html

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="LLM-MD-CLI — RAG-powered markdown document management" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <title>LLM-MD-CLI</title>
  </head>
  <body class="antialiased">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### 3.8 src/index.css

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --color-bg-primary: 255 255 255;
    --color-bg-secondary: 248 250 252;
    --color-bg-tertiary: 241 245 249;
    --color-border: 226 232 240;
    --color-text-primary: 15 23 42;
    --color-text-secondary: 71 85 105;
    --color-text-tertiary: 148 163 184;
  }

  .dark {
    --color-bg-primary: 15 23 42;
    --color-bg-secondary: 30 41 59;
    --color-bg-tertiary: 51 65 85;
    --color-border: 71 85 105;
    --color-text-primary: 248 250 252;
    --color-text-secondary: 203 213 225;
    --color-text-tertiary: 148 163 184;
  }

  body {
    @apply bg-surface text-slate-900 dark:bg-surface-dark-DEFAULT dark:text-slate-100;
  }

  * {
    @apply border-surface-border dark:border-surface-dark-border;
  }
}

@layer components {
  .scrollbar-thin {
    scrollbar-width: thin;
    scrollbar-color: theme('colors.slate.300') transparent;
  }

  .dark .scrollbar-thin {
    scrollbar-color: theme('colors.slate.600') transparent;
  }

  .scrollbar-thin::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }

  .scrollbar-thin::-webkit-scrollbar-track {
    background: transparent;
  }

  .scrollbar-thin::-webkit-scrollbar-thumb {
    @apply bg-slate-300 dark:bg-slate-600 rounded-full;
  }

  .prose-chat h1 { @apply text-xl font-bold mt-4 mb-2; }
  .prose-chat h2 { @apply text-lg font-semibold mt-3 mb-2; }
  .prose-chat h3 { @apply text-base font-semibold mt-2 mb-1; }
  .prose-chat p { @apply my-2 leading-relaxed; }
  .prose-chat ul { @apply list-disc pl-5 my-2; }
  .prose-chat ol { @apply list-decimal pl-5 my-2; }
  .prose-chat li { @apply my-0.5; }
  .prose-chat code { @apply bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-sm font-mono; }
  .prose-chat pre { @apply bg-slate-900 dark:bg-slate-950 rounded-lg p-4 my-3 overflow-x-auto; }
  .prose-chat pre code { @apply bg-transparent p-0; }
  .prose-chat blockquote { @apply border-l-4 border-brand-400 pl-4 italic my-3 text-slate-600 dark:text-slate-400; }
  .prose-chat a { @apply text-brand-600 dark:text-brand-400 underline underline-offset-2 hover:text-brand-700; }
  .prose-chat table { @apply w-full border-collapse my-3; }
  .prose-chat th { @apply border border-slate-300 dark:border-slate-600 px-3 py-2 bg-slate-50 dark:bg-slate-800 text-left font-semibold; }
  .prose-chat td { @apply border border-slate-300 dark:border-slate-600 px-3 py-2; }
}

@layer utilities {
  .animate-in {
    animation: fadeIn 0.2s ease-out, slideUp 0.3s ease-out;
  }
}
```

---

## 4. TypeScript Type System

### 4.1 src/types/index.ts — ALL types matching backend exactly

```typescript
// ============================================================
// API REQUEST TYPES (match backend Pydantic models exactly)
// ============================================================

export interface UploadRequest {
  file: File;
  namespace?: string;              // default: "default"
  tags?: string;                   // comma-separated
  webhook_url?: string;
  force_async?: boolean;           // default: false
}

export interface QueryRequest {
  query: string;                   // 1-10000 chars
  namespace?: string;              // default: "default"
  top_k?: number;                  // default: 5, range: 1-100
  filter?: Record<string, unknown>;
}

export interface AskRequest {
  question: string;                // 1-10000 chars
  namespace?: string;              // default: "default"
  top_k?: number;                  // default: 5, range: 1-20
  provider?: LLMProvider;          // default: "openai"
  model?: string;
  temperature?: number;            // default: 0.7, range: 0.0-2.0
  stream?: boolean;                // default: false
  thread_id?: string;
}

// ============================================================
// API RESPONSE TYPES (match backend response schemas exactly)
// ============================================================

export interface UploadResponse {
  status: 'success' | 'queued';
  file_name: string;
  chunks_created?: number;
  vectors_upserted?: number;
  namespace: string;
  job_id?: string;
  message?: string;
  webhook_url?: string;
}

export interface QueryResult {
  id: string;
  score: number;
  source: string;
  chunk_index: number;
  text: string;
  created_at?: string;
}

export interface QueryResponse {
  query: string;
  results: QueryResult[];
  namespace: string;
  total_results: number;
}

export interface SourceInfo {
  source: string;
  chunk_index: number;
  score: number;
}

export interface AskResponse {
  answer: string;
  sources: SourceInfo[];
  provider: string;
  model: string;
  thread_id?: string;
  has_context: boolean;
}

export interface ProviderInfo {
  name: LLMProvider;
  available: boolean;
  models: string[];
  error?: string;
}

export interface ProvidersResponse {
  providers: ProviderInfo[];
  default: {
    provider: string;
    model: string;
  };
}

export interface ConversationHistoryResponse {
  thread_id: string;
  messages: ConversationMessage[];
}

export interface DeleteConversationResponse {
  status: 'cleared';
  thread_id: string;
}

export interface IndexStats {
  name: string;
  total_vectors: number;
  dimension: number;
  namespaces: Record<string, { vector_count: number }>;
}

export interface StatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  index: IndexStats;
  embedding_model: string;
}

export interface DetailedHealthResponse {
  status: 'healthy' | 'degraded';
  checks: {
    api: string;
    redis: string;
    pinecone: string;
    pinecone_vectors?: number;
  };
}

export interface JobResult {
  file_name: string;
  chunks_created: number;
  vectors_upserted: number;
  namespace: string;
}

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  file_name: string;
  namespace: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  progress: number;
  chunks_total?: number;
  chunks_processed?: number;
  error?: string;
  result?: JobResult;
}

export interface JobListResponse {
  jobs: JobInfo[];
  count: number;
}

// ============================================================
// SSE STREAMING TYPES
// ============================================================

export type SSEEvent =
  | { type: 'sources'; data: SourceInfo[] }
  | { type: 'token'; data: string }
  | { type: 'thread_id'; data: string }
  | { type: 'done' }
  | { type: 'error'; data: string };

// ============================================================
// ENUMS & UNIONS
// ============================================================

export type LLMProvider = 'openai' | 'anthropic' | 'ollama';

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type Theme = 'light' | 'dark' | 'system';

export type ViewMode = 'list' | 'grid';

export type LayoutDensity = 'comfortable' | 'compact';

export type FontSize = 'small' | 'medium' | 'large';

export type ConnectionStatus = 'connected' | 'disconnected' | 'checking';

export type ScoreRange = 'excellent' | 'good' | 'fair' | 'low';

// ============================================================
// FRONTEND-ONLY TYPES (not from backend)
// ============================================================

export interface Conversation {
  id: string;
  title: string;
  namespace: string;
  provider: LLMProvider;
  model?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceInfo[];
  timestamp: string;
  is_streaming?: boolean;
}

export interface Activity {
  id: string;
  type: 'upload' | 'upload_complete' | 'chat' | 'error';
  description: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface SearchHistoryItem {
  id: string;
  query: string;
  namespace?: string;
  results_count: number;
  timestamp: string;
}

export interface NamespaceInfo {
  name: string;
  vector_count: number;
}

export interface UploadProgress {
  id: string;
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
  job_id?: string;
}

// ============================================================
// UTILITY TYPES
// ============================================================

export interface PaginationState {
  page: number;
  pageSize: number;
  total: number;
}

export interface SortState {
  field: string;
  direction: 'asc' | 'desc';
}

export interface FilterState {
  namespaces: string[];
  dateRange: 'all' | '24h' | 'week' | 'month';
  status?: JobStatus[];
}
```

---

## 5. API Client Layer

### 5.1 src/lib/api.ts

```typescript
import axios, { AxiosInstance, AxiosError, AxiosRequestConfig } from 'axios';
import type {
  UploadResponse,
  QueryRequest,
  QueryResponse,
  AskRequest,
  AskResponse,
  ProvidersResponse,
  ConversationHistoryResponse,
  DeleteConversationResponse,
  StatusResponse,
  DetailedHealthResponse,
  JobInfo,
  JobListResponse,
} from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 120_000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        const message =
          (error.response?.data as { detail?: string })?.detail ||
          error.message ||
          'An unexpected error occurred';
        console.error(`[API Error] ${error.config?.method?.toUpperCase()} ${error.config?.url}:`, message);
        return Promise.reject(new ApiError(message, error.response?.status));
      }
    );
  }

  // ---- Health ----
  async getHealth(): Promise<{ status: string }> {
    const { data } = await this.client.get('/health');
    return data;
  }

  async getDetailedHealth(): Promise<DetailedHealthResponse> {
    const { data } = await this.client.get('/health/detailed');
    return data;
  }

  // ---- Status ----
  async getStatus(): Promise<StatusResponse> {
    const { data } = await this.client.get('/api/status');
    return data;
  }

  // ---- Upload ----
  async uploadFile(
    file: File,
    namespace: string = 'default',
    tags: string = '',
    onProgress?: (percent: number) => void
  ): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('namespace', namespace);
    if (tags) formData.append('tags', tags);

    const config: AxiosRequestConfig = {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (event) => {
        if (event.total && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
        }
      },
    };

    const { data } = await this.client.post('/api/upload', formData, config);
    return data;
  }

  // ---- Query ----
  async query(request: QueryRequest): Promise<QueryResponse> {
    const { data } = await this.client.post('/api/query', request);
    return data;
  }

  async search(q: string, namespace?: string, limit?: number): Promise<QueryResponse> {
    const params: Record<string, string | number> = { q };
    if (namespace) params.namespace = namespace;
    if (limit) params.limit = limit;
    const { data } = await this.client.get('/api/search', { params });
    return data;
  }

  // ---- Chat (non-streaming) ----
  async ask(request: AskRequest): Promise<AskResponse> {
    const { data } = await this.client.post('/api/ask', { ...request, stream: false });
    return data;
  }

  // ---- Providers ----
  async getProviders(): Promise<ProvidersResponse> {
    const { data } = await this.client.get('/api/providers');
    return data;
  }

  // ---- Conversations ----
  async getConversation(threadId: string): Promise<ConversationHistoryResponse> {
    const { data } = await this.client.get(`/api/conversation/${threadId}`);
    return data;
  }

  async deleteConversation(threadId: string): Promise<DeleteConversationResponse> {
    const { data } = await this.client.delete(`/api/conversation/${threadId}`);
    return data;
  }

  // ---- Jobs ----
  async getJobs(namespace?: string, limit: number = 50): Promise<JobListResponse> {
    const params: Record<string, string | number> = { limit };
    if (namespace) params.namespace = namespace;
    const { data } = await this.client.get('/api/jobs', { params });
    return data;
  }

  async getJob(jobId: string): Promise<JobInfo> {
    const { data } = await this.client.get(`/api/jobs/${jobId}`);
    return data;
  }
}

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export const api = new ApiClient();
```

---

## 6. SSE Streaming Client

### 6.1 src/lib/streaming.ts

```typescript
import type { AskRequest, SSEEvent, SourceInfo } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export interface StreamCallbacks {
  onSources: (sources: SourceInfo[]) => void;
  onToken: (token: string) => void;
  onThreadId: (threadId: string) => void;
  onDone: () => void;
  onError: (error: string) => void;
}

/**
 * Streams a chat response from the backend using fetch + ReadableStream.
 * The backend uses FastAPI StreamingResponse with text/event-stream.
 * Returns an AbortController to allow cancelling the stream.
 */
export function streamChat(
  request: AskRequest,
  callbacks: StreamCallbacks
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...request, stream: true }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Stream request failed' }));
        callbacks.onError(errorData.detail || `HTTP ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError('No response body');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;

          const payload = trimmed.slice(6);

          if (payload === '[DONE]') {
            callbacks.onDone();
            return;
          }

          try {
            const parsed = JSON.parse(payload);

            if ('sources' in parsed) {
              callbacks.onSources(parsed.sources);
            } else if ('token' in parsed) {
              callbacks.onToken(parsed.token);
            } else if ('thread_id' in parsed) {
              callbacks.onThreadId(parsed.thread_id);
            } else if ('error' in parsed) {
              callbacks.onError(parsed.error);
            }
          } catch {
            // Skip malformed JSON lines
          }
        }
      }

      callbacks.onDone();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        callbacks.onDone();
      } else {
        callbacks.onError(err instanceof Error ? err.message : 'Stream failed');
      }
    }
  })();

  return controller;
}
```

---

## 7. State Management Architecture

### 7.1 Store Design Principles

Each Zustand store manages a SINGLE domain. TanStack Query handles server state caching and revalidation. Zustand handles only client-side UI state.

### 7.2 src/stores/settingsStore.ts

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Theme, LayoutDensity, FontSize, LLMProvider, ConnectionStatus } from '@/types';

interface SettingsState {
  // Connection
  backendUrl: string;
  connectionStatus: ConnectionStatus;

  // Defaults
  defaultNamespace: string;
  defaultProvider: LLMProvider;
  defaultModel: string;

  // Appearance
  theme: Theme;
  density: LayoutDensity;
  fontSize: FontSize;
  animationsEnabled: boolean;
  sidebarCollapsed: boolean;

  // Actions
  setBackendUrl: (url: string) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setDefaultNamespace: (ns: string) => void;
  setDefaultProvider: (provider: LLMProvider) => void;
  setDefaultModel: (model: string) => void;
  setTheme: (theme: Theme) => void;
  setDensity: (density: LayoutDensity) => void;
  setFontSize: (size: FontSize) => void;
  setAnimationsEnabled: (enabled: boolean) => void;
  toggleSidebar: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      backendUrl: import.meta.env.VITE_API_URL || 'http://localhost:8000',
      connectionStatus: 'disconnected',
      defaultNamespace: 'default',
      defaultProvider: 'openai',
      defaultModel: 'gpt-4o',
      theme: 'system',
      density: 'comfortable',
      fontSize: 'medium',
      animationsEnabled: true,
      sidebarCollapsed: false,

      setBackendUrl: (url) => set({ backendUrl: url }),
      setConnectionStatus: (status) => set({ connectionStatus: status }),
      setDefaultNamespace: (ns) => set({ defaultNamespace: ns }),
      setDefaultProvider: (provider) => set({ defaultProvider: provider }),
      setDefaultModel: (model) => set({ defaultModel: model }),
      setTheme: (theme) => set({ theme }),
      setDensity: (density) => set({ density }),
      setFontSize: (size) => set({ fontSize: size }),
      setAnimationsEnabled: (enabled) => set({ animationsEnabled: enabled }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    { name: 'llm-md-cli-settings' }
  )
);
```

### 7.3 src/stores/chatStore.ts

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Conversation, ConversationMessage, SourceInfo, LLMProvider } from '@/types';

interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: ConversationMessage[];
  isStreaming: boolean;
  streamingContent: string;
  streamingSources: SourceInfo[];
  abortController: AbortController | null;

  // Input
  inputText: string;
  selectedNamespace: string;
  selectedProvider: LLMProvider;
  selectedModel: string;
  temperature: number;

  // Actions
  setInputText: (text: string) => void;
  setSelectedNamespace: (ns: string) => void;
  setSelectedProvider: (provider: LLMProvider) => void;
  setSelectedModel: (model: string) => void;
  setTemperature: (temp: number) => void;
  setCurrentConversation: (id: string | null) => void;
  addConversation: (conv: Conversation) => void;
  removeConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  addMessage: (msg: ConversationMessage) => void;
  setMessages: (msgs: ConversationMessage[]) => void;
  setIsStreaming: (streaming: boolean) => void;
  appendStreamingContent: (token: string) => void;
  setStreamingSources: (sources: SourceInfo[]) => void;
  resetStreaming: () => void;
  setAbortController: (controller: AbortController | null) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      conversations: [],
      currentConversationId: null,
      messages: [],
      isStreaming: false,
      streamingContent: '',
      streamingSources: [],
      abortController: null,

      inputText: '',
      selectedNamespace: 'default',
      selectedProvider: 'openai',
      selectedModel: 'gpt-4o',
      temperature: 0.7,

      setInputText: (text) => set({ inputText: text }),
      setSelectedNamespace: (ns) => set({ selectedNamespace: ns }),
      setSelectedProvider: (provider) => set({ selectedProvider: provider }),
      setSelectedModel: (model) => set({ selectedModel: model }),
      setTemperature: (temp) => set({ temperature: temp }),
      setCurrentConversation: (id) => set({ currentConversationId: id }),
      addConversation: (conv) =>
        set((s) => ({ conversations: [conv, ...s.conversations] })),
      removeConversation: (id) =>
        set((s) => ({
          conversations: s.conversations.filter((c) => c.id !== id),
          currentConversationId: s.currentConversationId === id ? null : s.currentConversationId,
        })),
      renameConversation: (id, title) =>
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === id ? { ...c, title } : c
          ),
        })),
      addMessage: (msg) =>
        set((s) => ({ messages: [...s.messages, msg] })),
      setMessages: (msgs) => set({ messages: msgs }),
      setIsStreaming: (streaming) => set({ isStreaming: streaming }),
      appendStreamingContent: (token) =>
        set((s) => ({ streamingContent: s.streamingContent + token })),
      setStreamingSources: (sources) => set({ streamingSources: sources }),
      resetStreaming: () =>
        set({ streamingContent: '', streamingSources: [], isStreaming: false }),
      setAbortController: (controller) => set({ abortController: controller }),
    }),
    {
      name: 'llm-md-cli-chat',
      partialize: (state) => ({
        conversations: state.conversations,
        selectedNamespace: state.selectedNamespace,
        selectedProvider: state.selectedProvider,
        selectedModel: state.selectedModel,
        temperature: state.temperature,
      }),
    }
  )
);
```

### 7.4 src/stores/searchStore.ts

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { SearchHistoryItem } from '@/types';

interface SearchState {
  query: string;
  namespaces: string[];
  topK: number;
  minScore: number;
  dateRange: 'all' | '24h' | 'week' | 'month';
  history: SearchHistoryItem[];

  setQuery: (query: string) => void;
  setNamespaces: (ns: string[]) => void;
  setTopK: (k: number) => void;
  setMinScore: (score: number) => void;
  setDateRange: (range: 'all' | '24h' | 'week' | 'month') => void;
  addToHistory: (item: SearchHistoryItem) => void;
  clearHistory: () => void;
  clearFilters: () => void;
}

export const useSearchStore = create<SearchState>()(
  persist(
    (set) => ({
      query: '',
      namespaces: [],
      topK: 5,
      minScore: 0,
      dateRange: 'all',
      history: [],

      setQuery: (query) => set({ query }),
      setNamespaces: (ns) => set({ namespaces: ns }),
      setTopK: (k) => set({ topK: k }),
      setMinScore: (score) => set({ minScore: score }),
      setDateRange: (range) => set({ dateRange: range }),
      addToHistory: (item) =>
        set((s) => ({
          history: [item, ...s.history.filter((h) => h.query !== item.query)].slice(0, 20),
        })),
      clearHistory: () => set({ history: [] }),
      clearFilters: () =>
        set({ namespaces: [], topK: 5, minScore: 0, dateRange: 'all' }),
    }),
    {
      name: 'llm-md-cli-search',
      partialize: (state) => ({ history: state.history }),
    }
  )
);
```

---

## 8. Routing Configuration

### 8.1 src/App.tsx

```typescript
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { Layout } from '@/components/layout/Layout';
import { DashboardPage } from '@/pages/DashboardPage';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { SearchPage } from '@/pages/SearchPage';
import { ChatPage } from '@/pages/ChatPage';
import { JobsPage } from '@/pages/JobsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { ThemeProvider } from '@/components/layout/ThemeProvider';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

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
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RouterProvider router={router} />
        <Toaster
          position="bottom-right"
          toastOptions={{
            duration: 4000,
            style: {
              borderRadius: '10px',
              background: '#1e293b',
              color: '#f8fafc',
              fontSize: '14px',
            },
          }}
        />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
```

### 8.2 src/main.tsx

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

---

## 9. Design System & UI/UX Standards

### 9.1 UI/UX-MAX-PRO Principles (Embedded)

These standards MUST be applied across all pages and components:

#### Visual Hierarchy
- Use font weight (not just size) to distinguish levels: `font-bold` for primary, `font-semibold` for secondary, `font-medium` for tertiary
- Maximum 3 font sizes per screen section
- Primary actions use `bg-brand-600 hover:bg-brand-700` (filled buttons)
- Secondary actions use `border border-slate-300` (outline buttons)
- Destructive actions use `bg-red-600 hover:bg-red-700`

#### Spacing System
- Page padding: `p-6` (desktop), `p-4` (mobile)
- Section gap: `space-y-6`
- Card padding: `p-5`
- Between elements in a card: `space-y-3`
- Between icon and label: `gap-2`
- Between action buttons: `gap-2`

#### Interactive States (EVERY clickable element)
- Default → Hover → Active → Focus → Disabled
- Hover: `hover:bg-slate-50 dark:hover:bg-slate-800` for backgrounds
- Focus: `focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 focus:outline-none`
- Disabled: `opacity-50 cursor-not-allowed pointer-events-none`
- Active: `active:scale-[0.98]` for buttons
- Transitions: `transition-all duration-150 ease-out` on all interactive elements

#### Loading States
- Skeleton loading for initial data (never show empty containers)
- Inline spinners for button actions
- Shimmer effect for cards: `animate-shimmer bg-gradient-to-r from-slate-200 via-slate-100 to-slate-200 bg-[length:200%_100%]`
- Progress bars for uploads and jobs

#### Error States
- Inline errors below fields: `text-red-500 text-sm mt-1`
- Toast notifications for transient errors
- Full-screen error boundary with retry
- Empty states with illustration + CTA button

#### Micro-interactions
- Button press: `active:scale-[0.98] transition-transform`
- Card hover: `hover:shadow-card-hover transition-shadow duration-200`
- Modal enter: `animate-fade-in` + backdrop `animate-fade-in`
- List items: staggered `animate-slide-up` with `animation-delay`
- Score badges: color transitions on value change
- Sidebar collapse: `transition-[width] duration-300 ease-in-out`

#### Accessibility
- All interactive elements must have visible focus rings
- Color is never the ONLY indicator (always pair with icon/text)
- Minimum touch target: 44x44px on mobile
- ARIA labels on all icon-only buttons
- Keyboard navigation: Tab through all interactive elements
- Screen reader text via `sr-only` class where needed
- Reduced motion: respect `prefers-reduced-motion`

#### Responsive Breakpoints
- Mobile: `<768px` — single column, bottom nav, drawer menus
- Tablet: `768px-1279px` — 2 columns, collapsible sidebar
- Desktop: `≥1280px` — full layout with sidebar + content + optional panel

#### Dark Mode
- All colors must have dark variants using `dark:` prefix
- Never hardcode colors — always use semantic tokens (`surface`, `brand`, etc.)
- Test both themes for contrast ratio ≥ 4.5:1

### 9.2 src/lib/utils.ts — Utility functions

```typescript
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { formatDistanceToNow, format } from 'date-fns';
import type { ScoreRange } from '@/types';

/** Merge Tailwind classes with conflict resolution */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Format ISO date string to relative time ("2 hours ago") */
export function timeAgo(dateStr: string): string {
  return formatDistanceToNow(new Date(dateStr), { addSuffix: true });
}

/** Format ISO date string to readable format */
export function formatDate(dateStr: string): string {
  return format(new Date(dateStr), 'MMM d, yyyy HH:mm');
}

/** Classify similarity score into range */
export function getScoreRange(score: number): ScoreRange {
  if (score >= 0.9) return 'excellent';
  if (score >= 0.7) return 'good';
  if (score >= 0.5) return 'fair';
  return 'low';
}

/** Get Tailwind color class for score */
export function getScoreColor(score: number): string {
  const range = getScoreRange(score);
  const colors: Record<ScoreRange, string> = {
    excellent: 'text-score-excellent bg-green-50 dark:bg-green-950',
    good: 'text-score-good bg-blue-50 dark:bg-blue-950',
    fair: 'text-score-fair bg-yellow-50 dark:bg-yellow-950',
    low: 'text-score-low bg-slate-50 dark:bg-slate-800',
  };
  return colors[range];
}

/** Get score label */
export function getScoreLabel(score: number): string {
  const range = getScoreRange(score);
  const labels: Record<ScoreRange, string> = {
    excellent: 'Excellent',
    good: 'Good',
    fair: 'Fair',
    low: 'Low',
  };
  return labels[range];
}

/** Truncate text with ellipsis */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + '...';
}

/** Generate a UUID v4 */
export function generateId(): string {
  return crypto.randomUUID();
}

/** Format file size to human readable */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

/** Debounce a function */
export function debounce<T extends (...args: unknown[]) => unknown>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
```

---

## 10. File Structure (Complete)

```
frontend/
├── public/
│   ├── favicon.svg
│   └── icons/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Layout.tsx              → See IMPLEMENTATION_01
│   │   │   ├── Sidebar.tsx             → See IMPLEMENTATION_01
│   │   │   ├── Header.tsx              → See IMPLEMENTATION_01
│   │   │   ├── MobileNav.tsx           → See IMPLEMENTATION_01
│   │   │   └── ThemeProvider.tsx        → See IMPLEMENTATION_01
│   │   ├── ui/
│   │   │   ├── Button.tsx              → See IMPLEMENTATION_02
│   │   │   ├── Input.tsx               → See IMPLEMENTATION_02
│   │   │   ├── Select.tsx              → See IMPLEMENTATION_02
│   │   │   ├── Dialog.tsx              → See IMPLEMENTATION_02
│   │   │   ├── Badge.tsx               → See IMPLEMENTATION_02
│   │   │   ├── ProgressBar.tsx         → See IMPLEMENTATION_02
│   │   │   ├── Skeleton.tsx            → See IMPLEMENTATION_02
│   │   │   ├── EmptyState.tsx          → See IMPLEMENTATION_02
│   │   │   ├── FileUpload.tsx          → See IMPLEMENTATION_02
│   │   │   ├── DataTable.tsx           → See IMPLEMENTATION_02
│   │   │   ├── Tooltip.tsx             → See IMPLEMENTATION_02
│   │   │   ├── Dropdown.tsx            → See IMPLEMENTATION_02
│   │   │   └── MarkdownRenderer.tsx    → See IMPLEMENTATION_02
│   │   ├── dashboard/
│   │   │   ├── StatCard.tsx            → See IMPLEMENTATION_03
│   │   │   ├── QuickActionCard.tsx     → See IMPLEMENTATION_03
│   │   │   ├── ActivityList.tsx        → See IMPLEMENTATION_03
│   │   │   └── SystemStatus.tsx        → See IMPLEMENTATION_03
│   │   ├── documents/
│   │   │   ├── NamespaceTree.tsx       → See IMPLEMENTATION_04
│   │   │   ├── DocumentTable.tsx       → See IMPLEMENTATION_04
│   │   │   ├── DocumentGrid.tsx        → See IMPLEMENTATION_04
│   │   │   ├── UploadModal.tsx         → See IMPLEMENTATION_04
│   │   │   └── DocumentPreview.tsx     → See IMPLEMENTATION_04
│   │   ├── search/
│   │   │   ├── SearchInput.tsx         → See IMPLEMENTATION_05
│   │   │   ├── FilterPanel.tsx         → See IMPLEMENTATION_05
│   │   │   ├── ResultCard.tsx          → See IMPLEMENTATION_05
│   │   │   ├── ResultList.tsx          → See IMPLEMENTATION_05
│   │   │   └── SearchHistory.tsx       → See IMPLEMENTATION_05
│   │   ├── chat/
│   │   │   ├── ConversationList.tsx    → See IMPLEMENTATION_06
│   │   │   ├── MessageList.tsx         → See IMPLEMENTATION_06
│   │   │   ├── ChatMessage.tsx         → See IMPLEMENTATION_06
│   │   │   ├── ChatInput.tsx           → See IMPLEMENTATION_06
│   │   │   ├── ContextPanel.tsx        → See IMPLEMENTATION_06
│   │   │   ├── StreamingText.tsx       → See IMPLEMENTATION_06
│   │   │   └── MentionAutocomplete.tsx → See IMPLEMENTATION_06
│   │   ├── jobs/
│   │   │   ├── JobsTable.tsx           → See IMPLEMENTATION_07
│   │   │   ├── JobRow.tsx              → See IMPLEMENTATION_07
│   │   │   ├── JobStatusBadge.tsx      → See IMPLEMENTATION_07
│   │   │   ├── JobDetailModal.tsx      → See IMPLEMENTATION_07
│   │   │   └── JobFilters.tsx          → See IMPLEMENTATION_07
│   │   └── settings/
│   │       ├── SettingsLayout.tsx      → See IMPLEMENTATION_08
│   │       ├── GeneralSettings.tsx     → See IMPLEMENTATION_08
│   │       ├── ProviderSettings.tsx    → See IMPLEMENTATION_08
│   │       ├── EmbeddingSettings.tsx   → See IMPLEMENTATION_08
│   │       ├── AppearanceSettings.tsx  → See IMPLEMENTATION_08
│   │       ├── DataSettings.tsx        → See IMPLEMENTATION_08
│   │       └── AboutSection.tsx        → See IMPLEMENTATION_08
│   ├── pages/
│   │   ├── DashboardPage.tsx           → See IMPLEMENTATION_03
│   │   ├── DocumentsPage.tsx           → See IMPLEMENTATION_04
│   │   ├── SearchPage.tsx              → See IMPLEMENTATION_05
│   │   ├── ChatPage.tsx                → See IMPLEMENTATION_06
│   │   ├── JobsPage.tsx                → See IMPLEMENTATION_07
│   │   └── SettingsPage.tsx            → See IMPLEMENTATION_08
│   ├── hooks/
│   │   ├── useStatus.ts               → See IMPLEMENTATION_02
│   │   ├── useNamespaces.ts           → See IMPLEMENTATION_02
│   │   ├── useProviders.ts            → See IMPLEMENTATION_02
│   │   ├── useJobs.ts                 → See IMPLEMENTATION_02
│   │   ├── useSearch.ts               → See IMPLEMENTATION_02
│   │   ├── useUpload.ts               → See IMPLEMENTATION_02
│   │   ├── useChat.ts                 → See IMPLEMENTATION_02
│   │   ├── useKeyboard.ts            → See IMPLEMENTATION_02
│   │   └── useTheme.ts               → See IMPLEMENTATION_02
│   ├── stores/
│   │   ├── settingsStore.ts           → See Section 7.2
│   │   ├── chatStore.ts               → See Section 7.3
│   │   └── searchStore.ts            → See Section 7.4
│   ├── lib/
│   │   ├── api.ts                     → See Section 5.1
│   │   ├── streaming.ts              → See Section 6.1
│   │   └── utils.ts                  → See Section 9.2
│   ├── types/
│   │   └── index.ts                  → See Section 4.1
│   ├── constants/
│   │   └── index.ts                  → See IMPLEMENTATION_02
│   ├── App.tsx                        → See Section 8.1
│   ├── main.tsx                       → See Section 8.2
│   └── index.css                      → See Section 3.8
├── index.html                          → See Section 3.7
├── package.json                        → See Section 2.1
├── vite.config.ts                      → See Section 3.1
├── tsconfig.json                       → See Section 3.2
├── tsconfig.node.json                  → See Section 3.3
├── tailwind.config.js                  → See Section 3.4
├── postcss.config.js                   → See Section 3.5
├── .env                                → See Section 3.6
└── .eslintrc.cjs
```

---

## 11. Implementation Order

Execute these plans IN ORDER. Each plan is a self-contained implementation document:

| Order | File | Scope | Dependencies |
|-------|------|-------|--------------|
| 1 | `IMPLEMENTATION_01_FOUNDATION.md` | Layout, Sidebar, Header, ThemeProvider, MobileNav | This master plan |
| 2 | `IMPLEMENTATION_02_COMPONENTS.md` | All shared UI components + all custom hooks + constants | Plan 01 |
| 3 | `IMPLEMENTATION_03_DASHBOARD.md` | Dashboard page + dashboard components | Plan 01, 02 |
| 4 | `IMPLEMENTATION_04_DOCUMENTS.md` | Documents page + document components | Plan 01, 02 |
| 5 | `IMPLEMENTATION_05_SEARCH.md` | Search page + search components | Plan 01, 02 |
| 6 | `IMPLEMENTATION_06_CHAT.md` | Chat page + streaming + chat components | Plan 01, 02 |
| 7 | `IMPLEMENTATION_07_JOBS.md` | Jobs page + job components | Plan 01, 02 |
| 8 | `IMPLEMENTATION_08_SETTINGS.md` | Settings page + settings components | Plan 01, 02 |
| 9 | `IMPLEMENTATION_09_VALIDATION.md` | Browser testing checklist with MCP | All plans |

---

## 12. Cross-References

- **Backend API contracts:** All TypeScript types in Section 4.1 match the backend Pydantic models exactly
- **Backend routes prefix:** All API calls use `/api/` prefix, health uses `/health`
- **Backend streaming:** Uses FastAPI `StreamingResponse` with `text/event-stream` MIME type, NOT native WebSocket
- **Backend CORS:** Already enabled in `main.py` for frontend origin
- **Backend auth:** None (no authentication layer exists)
- **Backend pagination:** Jobs endpoint supports `limit` param (1-200), no offset-based pagination yet
- **Backend file types:** Upload only accepts `.md` files (validated server-side)
- **Backend async threshold:** Files > 100KB or > 20 chunks are processed asynchronously
- **Backend providers:** OpenAI (default), Anthropic, Ollama — factory pattern in `backend/llm/`
- **Backend embeddings:** `text-embedding-3-large` with 3072 dimensions via Pinecone

---

*This master plan provides the complete foundation. Proceed to IMPLEMENTATION_01_FOUNDATION.md next.*
