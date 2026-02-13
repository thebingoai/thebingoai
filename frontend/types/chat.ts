export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  sql_queries?: string[]
  results?: any[]
  success?: boolean
}

export interface ChatRequest {
  message: string
  connection_ids?: number[]
  thread_id?: string
}

export interface ChatResponse {
  thread_id: string
  message: string
  sql_queries?: string[]
  results?: any[]
  success: boolean
}

export interface Conversation {
  id: number
  thread_id: string
  title: string
  created_at: string
  updated_at: string
  messages?: ChatMessage[]
}
