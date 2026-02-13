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
