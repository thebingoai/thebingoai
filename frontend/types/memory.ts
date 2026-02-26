export interface Memory {
  id: string
  text: string
  date: string
  score: number
  metadata: Record<string, any>
}

export interface MemorySearchRequest {
  query: string
  top_k: number
}

export interface MemorySearchResponse {
  memories: Memory[]
}

export interface UserMemoryEntry {
  id: string
  content: string
  category: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserMemoryListResponse {
  entries: UserMemoryEntry[]
  total: number
}

export interface MemorySettings {
  memory_enabled: boolean
}

export interface MemoryHeatmapEntry {
  date: string
  count: number
}

export interface MemoryHeatmapResponse {
  data: MemoryHeatmapEntry[]
  total_days: number
  total_conversations: number
}
