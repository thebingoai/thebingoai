export * from './chart'

// ============================================================
// API REQUEST TYPES (match backend Pydantic models exactly)
// ============================================================

export interface UploadRequest {
  file: File
  namespace?: string // default: "default"
  tags?: string // comma-separated
  webhook_url?: string
  force_async?: boolean // default: false
}

export interface QueryRequest {
  query: string // 1-10000 chars
  namespace?: string // default: "default"
  top_k?: number // default: 5, range: 1-100
  filter?: Record<string, unknown>
}

export interface AskRequest {
  question: string // 1-10000 chars
  namespace?: string // default: "default"
  top_k?: number // default: 5, range: 1-20
  provider?: LLMProvider // default: "openai"
  model?: string
  temperature?: number // default: 0.7, range: 0.0-2.0
  stream?: boolean // default: false
  thread_id?: string
}

// ============================================================
// API RESPONSE TYPES (match backend response schemas exactly)
// ============================================================

export interface UploadResponse {
  status: 'success' | 'queued'
  file_name: string
  chunks_created?: number
  vectors_upserted?: number
  namespace: string
  job_id?: string
  message?: string
  webhook_url?: string
}

export interface QueryResult {
  id: string
  score: number
  source: string
  chunk_index: number
  text: string
  created_at?: string
}

export interface QueryResponse {
  query: string
  results: QueryResult[]
  namespace: string
  total_results: number
}

export interface SourceInfo {
  source: string
  chunk_index: number
  score: number
}

export interface AskResponse {
  answer: string
  sources: SourceInfo[]
  provider: string
  model: string
  thread_id?: string
  has_context: boolean
}

export interface ProviderInfo {
  name: LLMProvider
  available: boolean
  models: string[]
  error?: string
}

export interface ProvidersResponse {
  providers: ProviderInfo[]
  default: {
    provider: string
    model: string
  }
}

export interface ConversationHistoryResponse {
  thread_id: string
  messages: ConversationMessage[]
}

export interface DeleteConversationResponse {
  status: 'cleared'
  thread_id: string
}

export interface IndexStats {
  name: string
  total_vectors: number
  dimension: number
  namespaces: Record<string, { vector_count: number }>
}

export interface StatusResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  index: IndexStats
  embedding_model: string
}

export interface DetailedHealthResponse {
  status: 'healthy' | 'degraded'
  checks: {
    api: string
    redis: string
    pinecone: string
    pinecone_vectors?: number
  }
}

export interface JobResult {
  file_name: string
  chunks_created: number
  vectors_upserted: number
  namespace: string
}

export interface JobInfo {
  job_id: string
  status: JobStatus
  file_name: string
  namespace: string
  created_at: string
  started_at?: string
  completed_at?: string
  progress: number
  chunks_total?: number
  chunks_processed?: number
  error?: string
  result?: JobResult
}

export interface JobListResponse {
  jobs: JobInfo[]
  count: number
}

// ============================================================
// ENUMS & UNIONS
// ============================================================

export type LLMProvider = 'openai' | 'anthropic' | 'ollama'

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type Theme = 'light' | 'dark' | 'system'

export type ViewMode = 'list' | 'grid'

export type LayoutDensity = 'comfortable' | 'compact'

export type FontSize = 'small' | 'medium' | 'large'

export type ConnectionStatus = 'connected' | 'disconnected' | 'checking'

export type ScoreRange = 'excellent' | 'good' | 'fair' | 'low'

// ============================================================
// FRONTEND-ONLY TYPES (not from backend)
// ============================================================

export interface Conversation {
  id: string
  title: string
  namespace: string
  provider: LLMProvider
  model?: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceInfo[]
  timestamp: string
}

export interface Activity {
  id: string
  type: 'upload' | 'upload_complete' | 'chat' | 'error'
  description: string
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface SearchHistoryItem {
  id: string
  query: string
  namespace?: string
  results_count: number
  timestamp: string
}

export interface NamespaceInfo {
  name: string
  vector_count: number
}

export interface UploadProgress {
  id: string
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed'
  error?: string
  job_id?: string
}
