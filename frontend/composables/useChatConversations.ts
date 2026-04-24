import { useChatStore } from '~/stores/chat'
import type { Message, AgentStep } from '~/stores/chat'

/** Extract the best query result from persisted agent steps. */
function _extractQueryData(steps: AgentStep[]): { sql?: string; results: Record<string, any>[] } | null {
  let best: { sql?: string; columns: string[]; rows: any[][] } | null = null

  const check = (s: AgentStep) => {
    if (s.tool_name === 'execute_query' && s.step_type === 'tool_result') {
      const qd = s.content?.result?.query_data
      if (qd?.columns && qd?.rows) {
        if (!best || qd.rows.length >= best.rows.length) {
          best = { sql: qd.sql, columns: qd.columns, rows: qd.rows }
        }
      }
    }
  }

  for (const step of steps) {
    check(step)
    // Check nested steps inside data_agent tool results
    if (step.tool_name === 'data_agent' && step.step_type === 'tool_result') {
      for (const sub of step.content?.result?.steps || []) {
        check(sub as AgentStep)
      }
    }
  }

  if (!best) return null

  // Transform {columns, rows} → [{col: val}] for ChatMessageBubble
  const results = best.rows.map((row: any[]) => {
    const obj: Record<string, any> = {}
    best!.columns.forEach((col, i) => { obj[col] = row[i] ?? null })
    return obj
  })

  return { sql: best.sql, results }
}

export const useChatConversations = () => {
  const chatStore = useChatStore()
  const api = useApi()
  const ws = useWebSocket()
  const router = useRouter()
  const route = useRoute()

  const checkStreamingViaWs = (threadId: string) => {
    const sendCheck = () => {
      // One-shot handler for the stream.status response
      const unsubStatus = ws.on('stream.status', (data: any) => {
        if (data.thread_id !== threadId) return
        unsubStatus()

        if (!data.streaming) return // Already done, messages already loaded

        // Backend is still streaming — show indicator and wait for completion
        chatStore.isStreaming = true

        // Add a blank placeholder so the typing indicator renders correctly
        const hasAssistantPlaceholder = chatStore.messages.some(
          m => m.role === 'assistant' && !m.content
        )
        if (!hasAssistantPlaceholder) {
          chatStore.addMessage({
            id: `streaming-placeholder-${Date.now()}`,
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            agent_steps: [],
            thinking_steps: [],
          })
        }

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
      if (route.path === '/chat' && route.query.id !== threadId) {
        router.replace({ path: '/chat', query: { id: threadId } })
      }

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

                // Reconstruct sql + results from persisted execute_query steps
                const qd = _extractQueryData(agentSteps)
                if (qd) {
                  msgInStore.sql = qd.sql
                  msgInStore.results = qd.results
                }
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

  const mapConversation = (conv: any) => ({
    id: conv.thread_id,
    title: conv.title || 'Untitled',
    type: conv.type || 'task',
    created_at: conv.created_at,
    updated_at: conv.updated_at,
    message_count: conv.messages?.length || 0
  })

  const loadConversations = async () => {
    try {
      chatStore.resetConversationPagination()
      const response = await api.chat.getConversations() as any
      const conversations = (response.conversations || []).map(mapConversation)
      chatStore.setConversations(conversations)
      chatStore.conversationHasMore = response.has_more ?? false
      chatStore.conversationOffset = conversations.filter((c: any) => c.type === 'task').length

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

  const loadMoreConversations = async () => {
    if (!chatStore.conversationHasMore || chatStore.isLoadingMoreConversations) return
    chatStore.isLoadingMoreConversations = true
    try {
      const response = await api.chat.getConversations(false, true, chatStore.conversationOffset, 200) as any
      const conversations = (response.conversations || []).map(mapConversation)
      chatStore.appendConversations(conversations)
      chatStore.conversationHasMore = response.has_more ?? false
      chatStore.conversationOffset += conversations.filter((c: any) => c.type === 'task').length
    } catch (error) {
      console.error('Failed to load more conversations:', error)
    } finally {
      chatStore.isLoadingMoreConversations = false
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
      const conversations = (response.conversations || []).map(mapConversation)
      chatStore.setArchivedConversations(conversations)
    } catch (error) {
      console.error('Failed to load archived conversations:', error)
    }
  }

  return { loadConversations, loadMoreConversations, loadMessages, generateSummary, loadConversationSummary, renameConversation, archiveConversation, unarchiveConversation, loadArchivedConversations }
}
