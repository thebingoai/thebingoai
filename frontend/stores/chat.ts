import { defineStore } from 'pinia'
import type {
  Conversation,
  ConversationMessage,
  LLMProvider
} from '~/types'

export interface ChatState {
  // Conversations
  conversations: Conversation[]
  currentConversationId: string | null

  // Messages (for current conversation)
  messages: ConversationMessage[]

  // Loading state
  isLoading: boolean

  // Input state
  inputText: string

  // Chat settings (for new messages)
  selectedNamespace: string
  selectedProvider: LLMProvider
  selectedModel: string
  temperature: number
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    conversations: [],
    currentConversationId: null,
    messages: [],
    isLoading: false,
    inputText: '',
    selectedNamespace: 'default',
    selectedProvider: 'openai',
    selectedModel: '',
    temperature: 0.7
  }),

  getters: {
    currentConversation: (state): Conversation | null => {
      if (!state.currentConversationId) return null
      return state.conversations.find(c => c.id === state.currentConversationId) || null
    },

    sortedConversations: (state): Conversation[] => {
      return [...state.conversations].sort((a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )
    }
  },

  actions: {
    // Conversation management
    createConversation(title: string, threadId: string) {
      const conversation: Conversation = {
        id: threadId,
        title,
        namespace: this.selectedNamespace,
        provider: this.selectedProvider,
        model: this.selectedModel,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0
      }
      this.conversations.unshift(conversation)
      this.currentConversationId = threadId
    },

    setCurrentConversation(id: string | null) {
      this.currentConversationId = id
      if (!id) {
        this.messages = []
      }
    },

    updateConversation(id: string, updates: Partial<Conversation>) {
      const index = this.conversations.findIndex(c => c.id === id)
      if (index !== -1) {
        this.conversations[index] = {
          ...this.conversations[index],
          ...updates,
          updated_at: new Date().toISOString()
        }
      }
    },

    deleteConversation(id: string) {
      this.conversations = this.conversations.filter(c => c.id !== id)
      if (this.currentConversationId === id) {
        this.currentConversationId = null
        this.messages = []
      }
    },

    // Message management
    addMessage(message: ConversationMessage) {
      this.messages.push(message)
      if (this.currentConversationId) {
        const conversation = this.conversations.find(c => c.id === this.currentConversationId)
        if (conversation) {
          conversation.message_count = this.messages.length
          conversation.updated_at = new Date().toISOString()
        }
      }
    },

    updateLastMessage(updates: Partial<ConversationMessage>) {
      if (this.messages.length > 0) {
        const lastIndex = this.messages.length - 1
        this.messages[lastIndex] = {
          ...this.messages[lastIndex],
          ...updates
        }
      }
    },

    setMessages(messages: ConversationMessage[]) {
      this.messages = messages
    },

    // Loading state
    setLoading(val: boolean) {
      this.isLoading = val
    },

    // Input state
    setInputText(text: string) {
      this.inputText = text
    },

    clearInput() {
      this.inputText = ''
    },

    // Settings
    setSelectedNamespace(namespace: string) {
      this.selectedNamespace = namespace
    },

    setSelectedProvider(provider: LLMProvider) {
      this.selectedProvider = provider
    },

    setSelectedModel(model: string) {
      this.selectedModel = model
    },

    setTemperature(temp: number) {
      this.temperature = temp
    }
  },

  persist: {
    paths: [
      'conversations',
      'selectedNamespace',
      'selectedProvider',
      'selectedModel',
      'temperature'
    ]
  }
})
