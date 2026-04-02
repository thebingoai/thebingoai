import { useChatStore } from '~/stores/chat'
import type { Message, AgentStep } from '~/stores/chat'

export const useChatConversations = () => {
  const chatStore = useChatStore()
  const api = useApi()
  const ws = useWebSocket()

  const checkStreamingViaWs = (threadId: string) => {
    const sendCheck = () => {
      // One-shot handler for the stream.status response
      const unsubStatus = ws.on('stream.status', (data: any) => {
        if (data.thread_id !== threadId) return
        unsubStatus()

        if (!data.streaming) return // Already done, messages already loaded

        // Backend is still streaming — show indicator and wait for completion
        chatStore.isStreaming = true

        const unsubComplete = ws.on('chat.stream_complete', (evt: any) => {
          if (evt.thread_id !== threadId) return
          unsubComplete()
          clearTimeout(safetyTimeout)
          chatStore.isStreaming = false
          // Guard against stale notification if user navigated away
          if (chatStore.currentThreadId === threadId) {
            loadMessages(threadId)
          }
        })

        // Safety timeout — matches Redis TTL (5 min)
        const safetyTimeout = setTimeout(() => {
          unsubComplete()
          chatStore.isStreaming = false
        }, 5 * 60 * 1000)
      })

      ws.send({ type: 'stream.check', thread_id: threadId })
    }

    if (ws.isConnected.value) {
      sendCheck()
    } else {
      // WS hasn't reconnected yet — wait for it
      const unsubConnected = ws.on('connected', () => {
        unsubConnected()
        sendCheck()
      })
    }
  }

  const loadConversationSummary = async (threadId: string) => {
    try {
      const summary = await api.chat.getConversationSummary(threadId) as any
      if (summary && chatStore.currentThreadId === threadId) {
        chatStore.setConversationSummary({
          text: summary.text || '',
          updated_at: summary.updated_at || new Date().toISOString(),
          token_count: summary.token_count || 0,
          token_limit: summary.token_limit || 128000,
        })
      }
    } catch {
      // Summary may not exist yet — ignore silently
    }
  }

  const loadMessages = async (threadId: string) => {
    try {
      const conversation = await api.chat.getMessages(threadId) as any
      const messages: Message[] = (conversation.messages || []).map((msg: any, index: number) => ({
        id: msg.id ? String(msg.id) : `${threadId}-${index}`,
        role: msg.role,
        content: msg.content,
        source: msg.source || 'chat',
        created_at: msg.timestamp,
        attachments: msg.attachments?.map((a: any) => ({
          file_id: a.file_id,
          name: a.name,
          type: a.type,
          size: a.size,
          preview_url: null,
          status: 'ready' as const,
          storage_key: a.storage_key,
        })),
        agent_steps: [],
        thinking_steps: []
      }))
      messages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      chatStore.setMessages(messages)
      chatStore.setCurrentThread(threadId)

      // Resolve presigned URLs for image attachments
      const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])
      const imageRequests: Array<{ msgId: string; idx: number; fileId: string; storageKey?: string }> = []
      for (const msg of messages) {
        if (!msg.attachments) continue
        msg.attachments.forEach((att, idx) => {
          if (IMAGE_TYPES.has(att.type) && att.file_id && att.storage_key) {
            imageRequests.push({ msgId: msg.id, idx, fileId: att.file_id, storageKey: att.storage_key })
          }
        })
      }
      if (imageRequests.length > 0) {
        Promise.all(
          imageRequests.map(async ({ msgId, idx, fileId, storageKey }) => {
            try {
              const res = await api.chat.getFileUrl(fileId, storageKey) as { url: string }
              const msgInStore = chatStore.messages.find(m => m.id === msgId)
              if (msgInStore?.attachments?.[idx]) {
                msgInStore.attachments[idx].preview_url = res.url
              }
            } catch {
              // Silently fail — fallback icon will show
            }
          })
        )
      }

      // Load agent steps for assistant messages from chat source
      for (const msg of messages) {
        if (msg.role === 'assistant' && msg.source === 'chat' && msg.id && !msg.id.includes('-')) {
          try {
            const stepsResponse = await api.chat.getMessageSteps(threadId, msg.id) as any
            if (stepsResponse?.steps?.length > 0) {
              const agentSteps: AgentStep[] = stepsResponse.steps.map((s: any) => ({
                agent_type: s.agent_type,
                step_type: s.step_type,
                tool_name: s.tool_name,
                content: s.content || {},
                duration_ms: s.duration_ms,
                created_at: s.created_at
              }))
              const msgInStore = chatStore.messages.find(m => m.id === msg.id)
              if (msgInStore) {
                msgInStore.agent_steps = agentSteps
              }
            }
          } catch {
            // Steps may not exist for older messages — ignore silently
          }
        }
      }

      // Load conversation summary
      loadConversationSummary(threadId)

      // Check if backend is still streaming for this thread via WebSocket
      checkStreamingViaWs(threadId)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const loadConversations = async () => {
    try {
      const response = await api.chat.getConversations() as any
      const conversations = (response.conversations || []).map((conv: any) => ({
        id: conv.thread_id,
        title: conv.title || 'Untitled',
        type: conv.type || 'task',
        created_at: conv.created_at,
        updated_at: conv.updated_at,
        message_count: conv.messages?.length || 0
      }))
      chatStore.setConversations(conversations)

      // If hydrated thread exists and matches a known conversation, restore it
      if (chatStore.currentThreadId) {
        const match = conversations.find((c: any) => c.id === chatStore.currentThreadId)
        if (match) {
          await loadMessages(match.id)
          return
        }
      }

      // Auto-select permanent conversation if no active thread
      const permanent = conversations.find((c: any) => c.type === 'permanent')
      if (permanent && !chatStore.currentThreadId) {
        await loadMessages(permanent.id)
      }
    } catch (error) {
      console.error('Failed to load conversations:', error)
    }
  }

  const generateSummary = async () => {
    const threadId = chatStore.currentThreadId
    if (!threadId) return
    try {
      const summary = await api.chat.generateConversationSummary(threadId) as any
      if (summary && chatStore.currentThreadId === threadId) {
        chatStore.setConversationSummary({
          text: summary.text || '',
          updated_at: summary.updated_at || new Date().toISOString(),
          token_count: summary.token_count || 0,
          token_limit: summary.token_limit || 128000,
        })
      }
    } catch (error) {
      console.error('Failed to generate summary:', error)
    }
  }

  const renameConversation = async (threadId: string, title: string) => {
    await api.chat.updateTitle(threadId, title)
    chatStore.updateConversationTitle(threadId, title)
  }

  const archiveConversation = async (threadId: string) => {
    try {
      await api.chat.archiveConversation(threadId, true)
      chatStore.moveToArchived(threadId)
      // If we just archived the active conversation, navigate away
      if (chatStore.currentThreadId === threadId) {
        const permanent = chatStore.permanentConversation
        if (permanent) {
          await loadMessages(permanent.id)
        } else {
          chatStore.startNewChat()
        }
      }
    } catch (error) {
      console.error('Failed to archive conversation:', error)
    }
  }

  const unarchiveConversation = async (threadId: string) => {
    try {
      await api.chat.archiveConversation(threadId, false)
      chatStore.moveFromArchived(threadId)
    } catch (error) {
      console.error('Failed to unarchive conversation:', error)
    }
  }

  const loadArchivedConversations = async () => {
    try {
      const response = await api.chat.getConversations(true) as any
      const conversations = (response.conversations || []).map((conv: any) => ({
        id: conv.thread_id,
        title: conv.title || 'Untitled',
        type: conv.type || 'task',
        created_at: conv.created_at,
        updated_at: conv.updated_at,
        message_count: conv.messages?.length || 0
      }))
      chatStore.setArchivedConversations(conversations)
    } catch (error) {
      console.error('Failed to load archived conversations:', error)
    }
  }

  return { loadConversations, loadMessages, generateSummary, loadConversationSummary, renameConversation, archiveConversation, unarchiveConversation, loadArchivedConversations }
}
