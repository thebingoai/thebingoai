import { useChatStore } from '~/stores/chat'
import type { Message } from '~/stores/chat'

export const useChatWsHandlers = () => {
  const chatStore = useChatStore()
  const ws = useWebSocket()

  const resetContext = () => {
    if (!chatStore.currentThreadId) return
    const threadId = chatStore.currentThreadId
    const unsub = ws.on('context.reset_ack', (data: any) => {
      if (data.thread_id !== threadId) return
      unsub()
      chatStore.addMessage({
        id: String(data.message_id),
        role: 'system' as const,
        content: '',
        source: 'context_reset',
        created_at: data.timestamp,
        agent_steps: [],
        thinking_steps: [],
      })
    })
    ws.send({ type: 'context.reset', thread_id: threadId })
  }

  // Handle incoming title updates from WebSocket (arrives after chat.done)
  const registerTitleHandler = () => {
    return ws.on('chat.title', (data: any) => {
      const threadId = data.thread_id || chatStore.currentThreadId
      if (threadId) {
        chatStore.updateConversationTitle(threadId, data.content)
      }
    })
  }

  // Handle incoming summary updates from WebSocket (arrives after chat.done)
  const registerSummaryHandler = () => {
    return ws.on('chat.summary', (data: any) => {
      const threadId = data.thread_id || chatStore.currentThreadId
      if (threadId === chatStore.currentThreadId && data.content) {
        chatStore.setConversationSummary({
          text: data.content.text,
          updated_at: data.content.updated_at,
          token_count: data.content.token_count,
          token_limit: data.content.token_limit,
        })
      }
    })
  }

  // Handle incoming heartbeat messages from WebSocket
  const registerHeartbeatHandler = () => {
    return ws.on('heartbeat.message', (data: any) => {
      const threadId: string = data.thread_id
      const msg = data.message

      if (!msg) return

      const frontendMsg: Message = {
        id: String(msg.id),
        role: 'assistant',
        content: msg.content,
        source: 'heartbeat',
        created_at: msg.timestamp,
        agent_steps: [],
        thinking_steps: []
      }

      // If viewing the permanent conversation, append directly
      if (chatStore.currentThreadId === threadId) {
        chatStore.addMessage(frontendMsg)
      }

      // Increment unread count on the permanent conversation entry
      chatStore.incrementUnread(threadId)
    })
  }

  // Handle incoming skill suggestion notifications from WebSocket
  const registerSkillSuggestionsHandler = () => {
    return ws.on('skill_suggestions.new', (data: any) => {
      if (!data.suggestions?.length) return

      // Add to store (dedup)
      chatStore.addSkillSuggestions(data.suggestions)

      // Inject a skill_suggestion message into chat
      chatStore.addMessage({
        id: `skill-suggestion-${Date.now()}`,
        role: 'assistant',
        content: '',
        source: 'skill_suggestion',
        skillSuggestions: data.suggestions,
        created_at: new Date().toISOString(),
        agent_steps: [],
        thinking_steps: [],
      })
    })
  }

  return { registerTitleHandler, registerSummaryHandler, registerHeartbeatHandler, registerSkillSuggestionsHandler, resetContext }
}
