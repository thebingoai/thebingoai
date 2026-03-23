import { useChatStore } from '~/stores/chat'
import type { Message, AgentStep } from '~/stores/chat'
import { useChatFileUpload } from './useChatFileUpload'

export const useChat = () => {
  const chatStore = useChatStore()
  const api = useApi()
  const ws = useWebSocket()

  const sendMessage = async (message: string, fileIds: string[] = []) => {
    chatStore.isStreaming = true

    // Add user message optimistically
    const { attachedFiles } = useChatFileUpload()
    const attachments = attachedFiles.value
      .filter(f => f.status === 'ready' && f.file_id)
      .map(f => ({
        file_id: f.file_id!,
        name: f.file.name,
        type: f.file.type,
        size: f.file.size,
        preview_url: f.preview_url,
        status: 'ready' as const,
      }))

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
      attachments: attachments.length > 0 ? attachments : undefined,
    }
    chatStore.addMessage(userMessage)
    chatStore.clearInput()

    // Add empty assistant placeholder
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      thinking_steps: [],
      agent_steps: [],
      created_at: new Date().toISOString()
    }
    chatStore.addMessage(assistantMessage)

    const requestId = crypto.randomUUID()
    let accumulatedContent = ''
    let wordBuffer = ''
    const thinkingSteps: Array<{ step: string; description: string }> = []
    const agentSteps: AgentStep[] = []
    let currentReasoningText = ''

    // Register one-time handlers scoped to this request_id
    const unsubs: Array<() => void> = []

    const onEvent = (type: string, handler: (data: any) => void) => {
      unsubs.push(
        ws.on(type, (data: any) => {
          if (data.request_id && data.request_id !== requestId) return
          handler(data)
        })
      )
    }

    return new Promise<void>((resolve) => {
      const cleanup = () => {
        unsubs.forEach(fn => fn())
        chatStore.isStreaming = false
        resolve()
      }

      onEvent('chat.token', (data) => {
        const content = data.content || ''
        wordBuffer += content
        accumulatedContent += content
        const hasCompleteWord = /[\s\n.,!?;:]/.test(content)
        if (hasCompleteWord) {
          chatStore.updateLastMessage({ content: accumulatedContent })
          wordBuffer = ''
        }
      })

      onEvent('chat.reasoning_token', (data) => {
        const content = data.content || ''
        currentReasoningText += content

        // Auto-open reasoning panel on first reasoning token
        if (!chatStore.reasoningPanelOpen) {
          const lastMsg = chatStore.messages[chatStore.messages.length - 1]
          if (lastMsg) chatStore.openReasoningPanel(lastMsg.id)
        }

        // Update or create in-progress reasoning step
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.content.text = currentReasoningText
        } else {
          agentSteps.push({
            agent_type: 'orchestrator',
            step_type: 'reasoning',
            content: { text: currentReasoningText },
            status: 'streaming',
            started_at: Date.now()
          })
        }
        chatStore.updateLastMessage({ agent_steps: [...agentSteps] })
      })

      onEvent('chat.tool_call', (data) => {
        const toolName = data.content?.tool || data.tool || 'Tool'
        const args = data.content?.args || {}

        // Finalize any streaming reasoning step
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
        }
        currentReasoningText = ''

        agentSteps.push({
          agent_type: 'orchestrator',
          step_type: 'tool_call',
          tool_name: toolName,
          content: { args },
          status: 'started',
          started_at: Date.now()
        })
        thinkingSteps.push({ step: toolName, description: 'Running...' })
        chatStore.updateLastMessage({
          thinking_steps: [...thinkingSteps],
          agent_steps: [...agentSteps]
        })
      })

      onEvent('chat.reasoning', (data) => {
        // Finalize any streaming reasoning step
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
          lastStep.content.text = data.content?.text || lastStep.content.text
        } else {
          agentSteps.push({
            agent_type: 'orchestrator',
            step_type: 'reasoning',
            content: { text: data.content?.text || '' },
            status: 'completed',
            started_at: Date.now()
          })
        }
        currentReasoningText = ''
        chatStore.updateLastMessage({ agent_steps: [...agentSteps] })
      })

      onEvent('chat.tool_result', (data) => {
        const toolName = data.content?.tool || data.tool || 'Tool'
        const result = data.content?.result || {}
        const serverDuration = data.content?.duration_ms

        const lastPendingIdx = [...agentSteps].reverse().findIndex(
          s => s.step_type === 'tool_call' && s.status === 'started' && s.tool_name === toolName
        )
        if (lastPendingIdx !== -1) {
          const realIdx = agentSteps.length - 1 - lastPendingIdx
          const step = agentSteps[realIdx]
          step.status = 'completed'
          step.content.result = result
          step.duration_ms = serverDuration ?? (step.started_at ? Date.now() - step.started_at : undefined)
          if (result?.steps) step.content.sub_steps = result.steps
        }

        if (thinkingSteps.length > 0) {
          thinkingSteps[thinkingSteps.length - 1].description = 'Completed'
        }
        chatStore.updateLastMessage({
          thinking_steps: [...thinkingSteps],
          agent_steps: [...agentSteps]
        })
      })

      onEvent('chat.reasoning_end', (data) => {
        // The last reasoning block turned out to be the final answer, not reasoning.
        // Remove the streaming reasoning step so it doesn't appear in the panel.
        if (data.content?.is_final_answer) {
          const lastStep = agentSteps[agentSteps.length - 1]
          if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
            agentSteps.pop()
          }
          currentReasoningText = ''
          chatStore.updateLastMessage({ agent_steps: [...agentSteps] })
        }
      })

      onEvent('chat.status', (data) => {
        console.log('[WS] status:', data.content)
      })

      onEvent('chat.done', (data) => {
        if (wordBuffer) {
          chatStore.updateLastMessage({ content: accumulatedContent })
          wordBuffer = ''
        }

        // Finalize any leftover streaming reasoning step
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
          chatStore.updateLastMessage({ agent_steps: [...agentSteps] })
        }

        const threadId: string = data.thread_id
        if (threadId && !chatStore.currentThreadId) {
          chatStore.setCurrentThread(threadId)
          chatStore.addConversation({
            id: threadId,
            title: 'New Task',
            type: 'task',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 2
          })
        }
        cleanup()
      })

      onEvent('chat.title', (data) => {
        const threadId = data.thread_id || chatStore.currentThreadId
        if (threadId) {
          chatStore.updateConversationTitle(threadId, data.content)
        }
      })

      onEvent('chat.error', (data) => {
        // Finalize any streaming reasoning step on error
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
        }
        chatStore.updateLastMessage({ content: `Error: ${data.content}`, agent_steps: [...agentSteps] })
        cleanup()
      })

      onEvent('chat.rate_limited', (data) => {
        chatStore.rateLimitRetryAfter = data.retry_after || 0
        chatStore.updateLastMessage({ content: 'You\'ve reached your free tier limit. Please wait or add your own API key in Settings.' })
        cleanup()
      })

      // Send via WebSocket
      ws.send({
        type: 'chat.send',
        request_id: requestId,
        thread_id: chatStore.currentThreadId || null,
        message,
        connection_ids: [],
        file_ids: fileIds
      })
    })
  }

  const newChat = () => {
    chatStore.startNewChat()
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

  const loadMessages = async (threadId: string) => {
    try {
      const conversation = await api.chat.getMessages(threadId) as any
      const messages: Message[] = (conversation.messages || []).map((msg: any, index: number) => ({
        id: msg.id ? String(msg.id) : `${threadId}-${index}`,
        role: msg.role,
        content: msg.content,
        source: msg.source || 'chat',
        created_at: msg.timestamp,
        agent_steps: [],
        thinking_steps: []
      }))
      messages.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
      chatStore.setMessages(messages)
      chatStore.setCurrentThread(threadId)

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

      // Check if backend is still streaming for this thread via WebSocket
      checkStreamingViaWs(threadId)
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

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

  const renameConversation = async (threadId: string, title: string) => {
    await api.chat.updateTitle(threadId, title)
    chatStore.updateConversationTitle(threadId, title)
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

  return {
    sendMessage,
    newChat,
    loadConversations,
    loadMessages,
    renameConversation,
    registerHeartbeatHandler,
    resetContext,
  }
}
