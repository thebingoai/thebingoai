import { defineStore } from 'pinia'

export interface AgentStep {
  agent_type: string         // "orchestrator" | "data_agent" | "rag_agent"
  step_type: string          // "tool_call" | "tool_result" | "reasoning"
  tool_name?: string         // "data_agent", "execute_query", "list_tables", etc.
  content: Record<string, any>  // args, results, SQL, reasoning text
  duration_ms?: number
  status?: string            // "started" | "completed"
  started_at?: number        // Date.now() epoch ms captured on frontend during streaming
  created_at?: string        // ISO datetime from backend DB for historical messages
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  sql?: string
  results?: any[]
  thinking_steps?: ThinkingStep[]  // legacy - kept for backward compat
  agent_steps?: AgentStep[]
  steps_log?: string[]  // live steps log shown in chat bubble during streaming
  steps_log_collapsed?: boolean  // collapse steps log after final answer arrives
  created_at: string
  attachments?: FileAttachment[]
  source?: 'chat' | 'heartbeat' | 'system' | 'context_reset' | 'qa_answer'
}

export interface ThinkingStep {
  step: string
  description: string
}

export interface FileAttachment {
  name: string
  size: number
  type: string
  file_id: string | null
  preview_url: string | null
  status: 'uploading' | 'ready' | 'error'
  storage_key?: string
}

export interface Conversation {
  id: string
  title: string
  type: 'task' | 'permanent'
  is_archived?: boolean
  created_at: string
  updated_at: string
  message_count: number
  unread_count?: number
}

export interface ConversationSummary {
  text: string
  updated_at: string
  token_count: number
  token_limit: number
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [] as Conversation[],
    archivedConversations: [] as Conversation[],
    currentThreadId: null as string | null,
    messages: [] as Message[],
    inputText: '',
    attachedFiles: [] as File[],
    showUploadPanel: false,
    isStreaming: false,
    expandedThinking: new Set<string>(),
    infoPanelOpen: true,
    selectedMessageId: null as string | null,
    conversationSummary: null as ConversationSummary | null,
    infoPanelSections: {
      summary: true,
      datasets: true,
      dashboards: true,
      reasoning: true,
    } as Record<string, boolean>,
    rateLimitRetryAfter: 0
  }),

  getters: {
    currentConversation: (state) => {
      return state.conversations.find(c => c.id === state.currentThreadId)
    },
    permanentConversation: (state) => {
      return state.conversations.find(c => c.type === 'permanent') ?? null
    },
    taskConversations: (state) => {
      return state.conversations
        .filter(c => c.type === 'task')
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    },
    conversationDatasets: (state) => {
      return state.messages
        .filter(m => m.attachments?.length)
        .flatMap(m => m.attachments!.map(a => ({
          name: a.name,
          size: a.size,
          type: a.type,
          fileId: a.file_id,
          uploadedAt: m.created_at,
        })))
    },
    conversationDashboards: (state) => {
      const byId = new Map<number, { name: string; widgetCount: number; createdAt: string; dashboardId: number | null; action: string }>()
      for (const msg of state.messages) {
        for (const step of msg.agent_steps ?? []) {
          if (step.tool_name !== 'create_dashboard' && step.tool_name !== 'update_dashboard') continue
          try {
            const result = typeof step.content?.result === 'string'
              ? JSON.parse(step.content.result)
              : step.content?.result
            if (!result?.success) continue
            const id = result.dashboard_id ?? null
            // Extract name/widget count from result.message if not in dedicated fields
            let name = result.dashboard_name || step.content?.args?.name || ''
            let widgetCount = result.widget_count ?? 0
            if ((!name || !widgetCount) && result.message) {
              const nameMatch = result.message.match(/Dashboard\s+'([^']+)'/) || result.message.match(/\*\*([^*]+)\*\*\s*dashboard/i)
              if (nameMatch && !name) name = nameMatch[1]
              const countMatch = result.message.match(/(\d+)\s+widget/)
              if (countMatch && !widgetCount) widgetCount = parseInt(countMatch[1], 10)
            }
            // Deduplicate by dashboardId — merge best data across entries
            const key = id ?? -(byId.size + 1)
            const existing = byId.get(key)
            byId.set(key, {
              name: name || existing?.name || 'Dashboard',
              widgetCount: widgetCount || existing?.widgetCount || 0,
              createdAt: msg.created_at,
              dashboardId: id,
              action: step.tool_name === 'create_dashboard' ? 'Created' : 'Updated',
            })
          } catch { /* skip malformed */ }
        }
      }
      return Array.from(byId.values())
    }
  },

  actions: {
    setCurrentThread(threadId: string | null) {
      this.currentThreadId = threadId
      if (threadId) {
        localStorage.setItem('chat_currentThreadId', threadId)
      } else {
        localStorage.removeItem('chat_currentThreadId')
      }
    },

    hydrateFromStorage() {
      const stored = localStorage.getItem('chat_currentThreadId')
      if (stored) {
        this.currentThreadId = stored
      }
    },

    setMessages(messages: Message[]) {
      this.messages = messages
    },

    addMessage(message: Message) {
      this.messages.push(message)
    },

    updateLastMessage(updates: Partial<Message>) {
      if (this.messages.length > 0) {
        const lastMessage = this.messages[this.messages.length - 1]
        Object.assign(lastMessage, updates)
      }
    },

    setConversations(conversations: Conversation[]) {
      this.conversations = conversations
    },

    addConversation(conversation: Conversation) {
      this.conversations.unshift(conversation)
    },

    removeConversation(threadId: string) {
      this.conversations = this.conversations.filter(c => c.id !== threadId)
    },

    setArchivedConversations(conversations: Conversation[]) {
      this.archivedConversations = conversations
    },

    moveToArchived(threadId: string) {
      const conv = this.conversations.find(c => c.id === threadId)
      if (conv) {
        this.conversations = this.conversations.filter(c => c.id !== threadId)
        this.archivedConversations.unshift(conv)
      }
    },

    moveFromArchived(threadId: string) {
      const conv = this.archivedConversations.find(c => c.id === threadId)
      if (conv) {
        this.archivedConversations = this.archivedConversations.filter(c => c.id !== threadId)
        this.conversations.unshift(conv)
      }
    },

    updateConversationTitle(threadId: string, title: string) {
      const conversation = this.conversations.find(c => c.id === threadId)
      if (conversation) {
        conversation.title = title
      }
    },

    incrementUnread(threadId: string) {
      const conversation = this.conversations.find(c => c.id === threadId)
      // Only increment if this conversation is not currently selected
      if (conversation && this.currentThreadId !== threadId) {
        conversation.unread_count = (conversation.unread_count ?? 0) + 1
      }
    },

    clearUnread(threadId: string) {
      const conversation = this.conversations.find(c => c.id === threadId)
      if (conversation) {
        conversation.unread_count = 0
      }
    },

    toggleThinking(messageId: string) {
      if (this.expandedThinking.has(messageId)) {
        this.expandedThinking.delete(messageId)
      } else {
        this.expandedThinking.add(messageId)
      }
    },

    toggleUploadPanel() {
      this.showUploadPanel = !this.showUploadPanel
    },

    toggleInfoPanel() {
      this.infoPanelOpen = !this.infoPanelOpen
    },

    toggleInfoSection(key: string) {
      this.infoPanelSections[key] = !this.infoPanelSections[key]
    },

    selectMessageForReasoning(messageId: string) {
      this.selectedMessageId = messageId
      this.infoPanelSections.reasoning = true
    },

    clearReasoningSelection() {
      this.selectedMessageId = null
    },

    setConversationSummary(summary: ConversationSummary) {
      this.conversationSummary = summary
    },

    clearConversationSummary() {
      this.conversationSummary = null
    },

    clearInput() {
      this.inputText = ''
      this.attachedFiles = []
    },

    startNewChat() {
      this.currentThreadId = null
      this.messages = []
      this.inputText = ''
      this.attachedFiles = []
      this.isStreaming = false
      this.expandedThinking.clear()
      this.selectedMessageId = null
      this.conversationSummary = null
      localStorage.removeItem('chat_currentThreadId')
    },

    reset() {
      this.conversations = []
      this.archivedConversations = []
      this.currentThreadId = null
      this.messages = []
      this.inputText = ''
      this.attachedFiles = []
      this.isStreaming = false
      this.expandedThinking.clear()
      this.selectedMessageId = null
      this.conversationSummary = null
      localStorage.removeItem('chat_currentThreadId')
    }
  }
})
