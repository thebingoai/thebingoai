import type { ChatMessage, ChatRequest, ChatResponse, Conversation } from '~/types/chat'

export const useNewChat = () => {
  const auth = useAuthNew()
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)
  const currentThreadId = ref<string | null>(null)
  const conversations = ref<Conversation[]>([])

  async function sendMessage(request: ChatRequest) {
    loading.value = true

    messages.value.push({
      role: 'user',
      content: request.message,
      timestamp: new Date().toISOString()
    })

    try {
      const response = await auth.apiRequest<ChatResponse>('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          ...request,
          thread_id: currentThreadId.value
        })
      })

      messages.value.push({
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
        sql_queries: response.sql_queries,
        results: response.results,
        success: response.success
      })

      currentThreadId.value = response.thread_id
      return response
    } catch (error: any) {
      messages.value.push({
        role: 'assistant',
        content: `Error: ${error.message || 'Failed to process message'}`,
        timestamp: new Date().toISOString(),
        success: false
      })
      throw error
    } finally {
      loading.value = false
    }
  }

  async function loadConversations() {
    try {
      conversations.value = await auth.apiRequest<Conversation[]>('/api/chat/conversations')
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }

  async function loadConversation(threadId: string) {
    try {
      const conversation = await auth.apiRequest<Conversation>(`/api/chat/conversations/${threadId}`)
      messages.value = conversation.messages || []
      currentThreadId.value = threadId
    } catch (error) {
      console.error('Failed to load conversation:', error)
    }
  }

  function newConversation() {
    messages.value = []
    currentThreadId.value = null
  }

  return {
    messages,
    loading,
    currentThreadId,
    conversations,
    sendMessage,
    loadConversations,
    loadConversation,
    newConversation
  }
}
