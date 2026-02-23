import { defineStore } from 'pinia'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sql?: string
  results?: any[]
  thinking_steps?: ThinkingStep[]
  created_at: string
  attachments?: FileAttachment[]
}

export interface ThinkingStep {
  step: string
  description: string
}

export interface FileAttachment {
  name: string
  size: number
  type: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
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
    expandedThinking: new Set<string>()
  }),

  getters: {
    currentConversation: (state) => {
      return state.conversations.find(c => c.id === state.currentThreadId)
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

    clearInput() {
      this.inputText = ''
      this.attachedFiles = []
    },

    reset() {
      this.currentThreadId = null
      this.messages = []
      this.inputText = ''
      this.attachedFiles = []
      this.expandedThinking.clear()
    }
  }
})
