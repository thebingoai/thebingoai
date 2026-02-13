import { useChatStore } from '~/stores/chat'
import type { Message } from '~/stores/chat'

export const useChat = () => {
  const chatStore = useChatStore()
  const api = useApi()

  const sendMessage = async (message: string) => {
    chatStore.isStreaming = true

    // Add user message
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      created_at: new Date().toISOString()
    }
    chatStore.addMessage(userMessage)

    try {
      const response = await api.chat.send(message, chatStore.currentThreadId || undefined)

      // Add assistant message
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.message || 'Response received',
        sql: response.sql_queries?.[0],
        results: response.results,
        created_at: new Date().toISOString()
      }
      chatStore.addMessage(assistantMessage)

      // Update thread ID if new
      if (response.thread_id && !chatStore.currentThreadId) {
        chatStore.setCurrentThread(response.thread_id)
        chatStore.addConversation({
          id: response.thread_id,
          title: message.slice(0, 50),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          message_count: 2
        })
      }
    } catch (error: any) {
      console.error('Chat error:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        created_at: new Date().toISOString()
      }
      chatStore.addMessage(errorMessage)
    } finally {
      chatStore.isStreaming = false
      chatStore.clearInput()
    }
  }

  const newChat = () => {
    chatStore.reset()
  }

  const loadConversations = async () => {
    try {
      const response = await api.chat.getConversations() as any
      // Backend returns { conversations: ConversationResponse[] }
      // Map to frontend Conversation type
      const conversations = (response.conversations || []).map((conv: any) => ({
        id: conv.thread_id,
        title: conv.title || 'Untitled',
        created_at: conv.created_at,
        updated_at: conv.updated_at,
        message_count: conv.messages?.length || 0
      }))
      chatStore.setConversations(conversations)
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }

  const loadMessages = async (threadId: string) => {
    try {
      // Backend returns ConversationResponse with embedded messages
      const conversation = await api.chat.getMessages(threadId) as any
      // Map ChatMessage[] to frontend Message type
      const messages = (conversation.messages || []).map((msg: any, index: number) => ({
        id: `${threadId}-${index}`,
        role: msg.role,
        content: msg.content,
        created_at: msg.timestamp
      }))
      chatStore.setMessages(messages)
      chatStore.setCurrentThread(threadId)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  return {
    sendMessage,
    newChat,
    loadConversations,
    loadMessages
  }
}
