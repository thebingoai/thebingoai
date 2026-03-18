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
  created_at: string
  attachments?: FileAttachment[]
  source?: 'chat' | 'heartbeat' | 'system' | 'context_reset'
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
}

export interface Conversation {
  id: string
  title: string
  type: 'task' | 'permanent'
  created_at: string
  updated_at: string
  message_count: number
  unread_count?: number
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [] as Conversation[],
    currentThreadId: null as string | null,
    messages: [] as Message[],
    inputText: '',
    attachedFiles: [] as File[],
    showUploadPanel: false,
    isStreaming: false,
    expandedThinking: new Set<string>(),
    reasoningPanelOpen: false,
    selectedMessageId: null as string | null
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
    }
  },

  actions: {
    setCurrentThread(threadId: string | null) {
      this.currentThreadId = threadId
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

    openReasoningPanel(messageId: string) {
      this.selectedMessageId = messageId
      this.reasoningPanelOpen = true
    },

    closeReasoningPanel() {
      this.reasoningPanelOpen = false
      this.selectedMessageId = null
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
      this.reasoningPanelOpen = false
      this.selectedMessageId = null
    },

    reset() {
      this.conversations = []
      this.currentThreadId = null
      this.messages = []
      this.inputText = ''
      this.attachedFiles = []
      this.isStreaming = false
      this.expandedThinking.clear()
      this.reasoningPanelOpen = false
      this.selectedMessageId = null
    }
  }
})
