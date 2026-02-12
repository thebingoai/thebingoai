import type { AskRequest } from '~/types'
import { toast } from 'vue-sonner'
import { MESSAGES } from '~/utils/constants'

export const useChat = () => {
  const chatStore = useChatStore()
  const api = useApi()

  const sendMessage = async (question: string) => {
    if (!question.trim()) return

    // Create user message
    const userMessage = {
      id: `${Date.now()}-user`,
      role: 'user' as const,
      content: question,
      timestamp: new Date().toISOString()
    }

    chatStore.addMessage(userMessage)
    chatStore.clearInput()

    // Create assistant message placeholder
    const assistantMessage = {
      id: `${Date.now()}-assistant`,
      role: 'assistant' as const,
      content: '',
      timestamp: new Date().toISOString()
    }

    chatStore.addMessage(assistantMessage)
    chatStore.setLoading(true)

    const request: AskRequest = {
      question,
      namespace: chatStore.selectedNamespace,
      provider: chatStore.selectedProvider,
      model: chatStore.selectedModel || undefined,
      temperature: chatStore.temperature,
      thread_id: chatStore.currentConversationId || undefined,
      stream: false
    }

    try {
      const response = await api.ask(request)

      // Update the assistant message with response
      chatStore.updateLastMessage({
        content: response.answer,
        sources: response.sources
      })

      // Create new conversation if this is the first message
      if (!chatStore.currentConversationId && response.thread_id) {
        const title = question.slice(0, 50) + (question.length > 50 ? '...' : '')
        chatStore.createConversation(title, response.thread_id)
      }
    } catch (err: any) {
      toast.error(err.message || MESSAGES.CHAT_ERROR)
      // Remove the failed assistant message
      chatStore.messages.pop()
    } finally {
      chatStore.setLoading(false)
    }
  }

  return {
    sendMessage
  }
}
