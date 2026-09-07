import { defineStore } from 'pinia'
import type { SkillSuggestion } from '~/types/skillSuggestion'
import { trackEvent } from '~/utils/analytics'

export interface AgentStep {
  agent_type: string         // "orchestrator" | "data_agent" | "rag_agent"
  step_type: string          // "tool_call" | "tool_result" | "reasoning" | "judge_status"
  tool_name?: string         // "data_agent", "execute_query", "list_tables", etc.
  content: Record<string, any>  // args, results, reasoning text, or {state} for judge_status
  duration_ms?: number
  status?: string            // "started" | "completed" | "streaming"
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
  steps_log_expanded?: boolean  // user-toggled; defaults to collapsed
  created_at: string
  attachments?: FileAttachment[]
  source?: 'chat' | 'heartbeat' | 'system' | 'context_reset' | 'qa_answer' | 'skill_suggestion' | 'dataset_docs'
  skillSuggestions?: SkillSuggestion[]
  loop_detected?: boolean
  briefing_id?: number | null
  query_files?: QueryFile[]  // downloadable datasets produced by this turn's queries
  values_withheld?: boolean  // privacy floor kept the rows from the LLM; the bubble renders them instead
  chart_specs?: ChartRef[] | null
}

export interface QueryFile {
  result_ref: string
  label: string
  row_count: number
  col_count: number
}

export type ChartRef =
  | { kind: 'adhoc'; widget: Record<string, any>; connection_id: number }
  | { kind: 'dashboard_widget'; dashboard_id: number; widget_id: string }

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

export interface DatasetDocsColumn {
  name: string
  display_name: string | null
  description: string | null
}

/** The `dataset.docs` WebSocket payload: what Bingo read a dataset's columns as. */
export interface DatasetDocs {
  connection_id: number
  table_name: string
  filename: string | null
  table_description: string | null
  // Column order follows the connection's stored context, which is not schema order.
  columns: DatasetDocsColumn[]
  total_columns: number
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
    conversationsLoaded: false,
    archivedConversations: [] as Conversation[],
    currentThreadId: (() => {
      try { return localStorage.getItem('chat_currentThreadId') }
      catch { return null }
    })() as string | null,
    messages: [] as Message[],
    messagesLoading: false,
    // Connections whose dataset documentation is still being generated. Profiling
    // finishes well before the LLM does, so the dataset's own step can't be used
    // to keep the "Reading your data…" state up until the docs message lands.
    // Keyed by connection, not thread: upload two files and the first one's docs
    // must not clear the second one's progress.
    docsPendingConnections: [] as number[],
    // The structured `dataset.docs` payload, keyed by connection id. Written when
    // documentation completes; the empty terminal event stores a zero-column entry.
    datasetDocs: {} as Record<number, DatasetDocs>,
    // Per-thread cache of fully-loaded messages (incl. agent_steps). Lets a task
    // viewed once this session reopen instantly without refetching. Invalidated
    // for a thread when a new message is sent to it (its history changed).
    messageCache: {} as Record<string, Message[]>,
    inputText: '',
    // Connection ids to force on the NEXT chat message (set by onboarding first-question).
    // Cleared by useChatStreaming after the send so it only applies once.
    pendingConnectionIds: [] as number[],
    attachedFiles: [] as File[],
    showUploadPanel: false,
    isStreaming: false,
    expandedThinking: new Set<string>(),
    // Closed by default — the upload flow now plays out in the thread itself,
    // so the panel opening on its own just steals width from the content.
    infoPanelOpen: false,
    selectedMessageId: null as string | null,
    conversationSummary: null as ConversationSummary | null,
    skillSuggestions: [] as SkillSuggestion[],
    infoPanelSections: {
      summary: true,
      datasets: true,
      dashboards: true,
      skills: true,
      reasoning: false,
    } as Record<string, boolean>,
    rateLimitRetryAfter: 0,
    conversationHasMore: false,
    conversationOffset: 0,
    isLoadingMoreConversations: false,
    pendingNewConversationId: null as string | null,
  }),

  getters: {
    currentConversation: (state) => {
      return state.conversations.find(c => c.id === state.currentThreadId)
    },
    /**
     * currentThreadId, but only when it names a conversation the server knows.
     *
     * The dashboard empty state parks a local `pending-<ts>` placeholder here
     * while it navigates, so anything crossing the network must read this
     * instead — the backend answers "Conversation not found" for an id it never
     * issued, and a null tells it to create the conversation as usual.
     */
    realThreadId: (state): string | null => {
      const id = state.currentThreadId
      return !id || id.startsWith('pending-') ? null : id
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
    },
    pendingSkillSuggestions: (state) => {
      return state.skillSuggestions.filter(s => s.status === 'pending')
    },
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
      try {
        const stored = localStorage.getItem('chat_currentThreadId')
        if (stored) {
          this.currentThreadId = stored
        }
      } catch { /* localStorage may not be available */ }
    },

    setMessages(messages: Message[]) {
      this.messages = messages
    },

    cacheMessages(threadId: string, messages: Message[]) {
      this.messageCache[threadId] = messages
    },

    invalidateMessageCache(threadId: string) {
      delete this.messageCache[threadId]
    },

    addMessage(message: Message) {
      // GA4 chat_message_sent / chat_response_received are NOT fired here — this is
      // also hit by heartbeat relays, Telegram relays, skill suggestions, and the
      // reconnect placeholder, which would inflate both events. chat_message_sent
      // fires in useChatStreaming.sendMessage (where the in-app user message is
      // created); chat_response_received fires once at stream completion there.
      this.messages.push(message)
    },

    updateLastMessage(updates: Partial<Message>) {
      if (this.messages.length > 0) {
        const lastMessage = this.messages[this.messages.length - 1]
        Object.assign(lastMessage, updates)
      }
    },

    updateMessageById(id: string, updates: Partial<Message>) {
      const msg = this.messages.find(m => m.id === id)
      if (msg) {
        Object.assign(msg, updates)
      }
    },

    setConversations(conversations: Conversation[]) {
      this.conversations = conversations
      this.conversationsLoaded = true
    },

    appendConversations(conversations: Conversation[]) {
      const existingIds = new Set(this.conversations.map(c => c.id))
      const newConvs = conversations.filter(c => !existingIds.has(c.id))
      this.conversations.push(...newConvs)
    },

    resetConversationPagination() {
      this.conversationHasMore = false
      this.conversationOffset = 0
      this.isLoadingMoreConversations = false
    },

    addConversation(conversation: Conversation) {
      this.conversations.unshift(conversation)
    },

    replacePendingConversation(realConv: Conversation) {
      const idx = this.conversations.findIndex(c => c.id === this.pendingNewConversationId)
      if (idx !== -1) {
        this.conversations.splice(idx, 1, realConv)
      } else if (!this.conversations.find(c => c.id === realConv.id)) {
        this.conversations.unshift(realConv)
      }
      this.pendingNewConversationId = null
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
        if (this.conversationOffset > 0) this.conversationOffset--
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

    updateConversationActivity(threadId: string, updatedAt: string) {
      const conversation = this.conversations.find(c => c.id === threadId)
      if (conversation) {
        conversation.updated_at = updatedAt
      }
    },

    markDocsPending(connectionId: number) {
      if (!this.docsPendingConnections.includes(connectionId)) {
        this.docsPendingConnections.push(connectionId)
      }
    },

    clearDocsPending(connectionId: number) {
      this.docsPendingConnections = this.docsPendingConnections.filter(id => id !== connectionId)
    },

    setDatasetDocs(docs: DatasetDocs) {
      this.datasetDocs[docs.connection_id] = docs
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

    setSkillSuggestions(suggestions: SkillSuggestion[]) {
      this.skillSuggestions = suggestions
    },

    addSkillSuggestions(suggestions: SkillSuggestion[]) {
      const existingIds = new Set(this.skillSuggestions.map(s => s.id))
      for (const s of suggestions) {
        if (!existingIds.has(s.id)) {
          this.skillSuggestions.push(s)
        }
      }
    },

    removeSkillSuggestion(id: string) {
      this.skillSuggestions = this.skillSuggestions.filter(s => s.id !== id)
    },

    startNewChat() {
      trackEvent('chat_start')
      this.currentThreadId = null
      this.messages = []
      this.inputText = ''
      this.pendingConnectionIds = []
      this.attachedFiles = []
      this.isStreaming = false
      this.expandedThinking.clear()
      this.selectedMessageId = null
      this.conversationSummary = null
      localStorage.removeItem('chat_currentThreadId')
    },

    reset() {
      this.conversations = []
      this.conversationsLoaded = false
      this.archivedConversations = []
      this.currentThreadId = null
      this.messages = []
      this.messageCache = {}
      this.inputText = ''
      this.attachedFiles = []
      this.isStreaming = false
      this.expandedThinking.clear()
      this.selectedMessageId = null
      this.conversationSummary = null
      this.conversationHasMore = false
      this.conversationOffset = 0
      this.isLoadingMoreConversations = false
      localStorage.removeItem('chat_currentThreadId')
    }
  }
})
