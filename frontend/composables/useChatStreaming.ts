import { useChatStore } from '~/stores/chat'
import type { Message, AgentStep } from '~/stores/chat'
import { useChatFileUpload } from './useChatFileUpload'

export const useChatStreaming = () => {
  const chatStore = useChatStore()
  const ws = useWebSocket()
  const { refresh: refreshCredits } = useCreditBalance()

  const sendMessage = async (message: string, fileIds: string[] = [], options?: { source?: Message['source'] }) => {
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
      source: options?.source,
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
    const assistantMsgId = assistantMessage.id

    const requestId = crypto.randomUUID()
    let accumulatedContent = ''
    let displayedContent = ''
    let dripTimer: ReturnType<typeof setInterval> | null = null
    const DRIP_INTERVAL = 20 // ms per tick
    const CHARS_PER_TICK = 1 // characters revealed per tick (~50 chars/sec)
    const thinkingSteps: Array<{ step: string; description: string }> = []
    const agentSteps: AgentStep[] = []
    let currentReasoningText = ''
    let acknowledgeText = ''
    const stepsLog: string[] = []

    /** Extract compact arg summary for the steps log (skip connection_id, show key value). */
    const compactArg = (args: Record<string, any>): string => {
      const meaningful = Object.entries(args).filter(([k]) => k !== 'connection_id' && k !== 'sql' && !k.startsWith('_'))
      if (meaningful.length === 0) return ''
      const [key, val] = meaningful[0]
      const str = typeof val === 'string' ? val : JSON.stringify(val)
      // Show full request text for plan-like args (create_dashboard, update_dashboard)
      if (key === 'request') return str
      return str.length > 80 ? str.slice(0, 77) + '...' : str
    }

    const formatToolLabel = (name: string): string =>
      name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())

    const formatTs = (): string =>
      new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

    /** Push steps_log to the message so ChatMessageBubble can render it. */
    const syncStepsLog = () => {
      chatStore.updateMessageById(assistantMsgId, { steps_log: [...stepsLog] })
    }

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

    // Ensure WebSocket is connected (refresh token + reconnect if needed)
    if (!ws.isConnected.value) {
      try {
        const authStore = useAuthStore()
        const ok = await authStore.refreshAccessToken()
        if (!ok) throw new Error('Session expired')
        ws.connect(authStore.token!)
        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => { unsub(); reject(new Error('WebSocket reconnect timeout')) }, 10_000)
          const unsub = ws.on('connected', () => { unsub(); clearTimeout(timeout); resolve() })
        })
      } catch (err: any) {
        chatStore.updateMessageById(assistantMsgId, { content: `Error: ${err.message}. Please log in again.` })
        chatStore.isStreaming = false
        return
      }
    }

    return new Promise<void>((resolve) => {
      const cleanup = () => {
        flushContentDrip()
        unsubs.forEach(fn => fn())
        chatStore.isStreaming = false
        resolve()
      }

      // Drip buffer — release characters at a readable pace instead of raw streaming speed
      const startContentDrip = () => {
        if (dripTimer) return
        dripTimer = setInterval(() => {
          if (displayedContent.length >= accumulatedContent.length) return
          displayedContent = accumulatedContent.slice(0, displayedContent.length + CHARS_PER_TICK)
          chatStore.updateMessageById(assistantMsgId, { content: displayedContent, steps_log_expanded: false })
        }, DRIP_INTERVAL)
      }

      const flushContentDrip = () => {
        if (dripTimer) { clearInterval(dripTimer); dripTimer = null }
        if (displayedContent !== accumulatedContent) {
          displayedContent = accumulatedContent
          chatStore.updateMessageById(assistantMsgId, { content: displayedContent })
        }
      }

      onEvent('chat.token', (data) => {
        accumulatedContent += (data.content || '')
        startContentDrip()
      })

      onEvent('chat.reasoning_token', (data) => {
        const content = data.content || ''
        currentReasoningText += content

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

        acknowledgeText = currentReasoningText
        chatStore.updateMessageById(assistantMsgId, { agent_steps: [...agentSteps] })
      })

      onEvent('chat.tool_call', (data) => {
        const toolName = data.content?.tool || data.tool || 'Tool'
        const args = data.content?.args || {}

        // Finalize any streaming reasoning step and add to steps log
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
          // Add reasoning to steps log if not already added
          if (stepsLog.length === 0 && acknowledgeText) {
            const preview = acknowledgeText.length > 80 ? acknowledgeText.slice(0, 77) + '...' : acknowledgeText
            stepsLog.push(`${formatTs()}  ● ${preview}`)
          }
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

        // Append to live steps log in chat bubble
        const label = formatToolLabel(toolName)
        const argSummary = compactArg(args)
        const ts = formatTs()
        stepsLog.push(argSummary ? `${ts}  › ${label} — ${argSummary}` : `${ts}  › ${label}`)
        syncStepsLog()

        chatStore.updateMessageById(assistantMsgId, {
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
        chatStore.updateMessageById(assistantMsgId, { agent_steps: [...agentSteps] })
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

        // Update steps log with duration — find last entry without a duration marker
        const label = formatToolLabel(toolName)
        const logIdx = stepsLog.findLastIndex(l => l.includes(`› ${label}`) && !l.includes('(') && !l.includes('✓'))
        if (logIdx !== -1) {
          if (typeof serverDuration === 'number') {
            const durStr = serverDuration < 1000 ? `${serverDuration}ms` : `${(serverDuration / 1000).toFixed(1)}s`
            stepsLog[logIdx] = stepsLog[logIdx] + ` (${durStr})`
          } else {
            stepsLog[logIdx] = stepsLog[logIdx] + ' ✓'
          }
          syncStepsLog()
        }

        chatStore.updateMessageById(assistantMsgId, {
          thinking_steps: [...thinkingSteps],
          agent_steps: [...agentSteps]
        })
      })

      onEvent('query.result', (data) => {
        const payload = data.data || {}
        const columns: string[] = payload.columns || []
        const rawRows: any[][] = payload.rows || []

        // Transform [columns] + [[row]] into [{col: val}] for ChatMessageBubble
        const results = rawRows.slice(0, 50).map((row: any[]) => {
          const obj: Record<string, any> = {}
          columns.forEach((col, i) => { obj[col] = row[i] ?? null })
          return obj
        })

        // Keep the result with the most rows when multiple queries run in one turn
        const targetMsg = chatStore.messages.find(m => m.id === assistantMsgId)
        if (!targetMsg?.results?.length || results.length >= (targetMsg.results?.length || 0)) {
          chatStore.updateMessageById(assistantMsgId, {
            sql: payload.sql || undefined,
            results,
          })
        }
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
          chatStore.updateMessageById(assistantMsgId, { steps_log_expanded: false, agent_steps: [...agentSteps] })
        }
      })

      onEvent('chat.status', (data) => {
        console.log('[WS] status:', data.content)
      })

      onEvent('chat.done', (data) => {
        flushContentDrip()

        // Finalize any leftover streaming reasoning step
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
          chatStore.updateMessageById(assistantMsgId, { agent_steps: [...agentSteps] })
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

        // Refresh credit balance after each turn so the badge stays current
        refreshCredits()

        cleanup()
      })

      onEvent('chat.error', (data) => {
        // Finalize any streaming reasoning step on error
        const lastStep = agentSteps[agentSteps.length - 1]
        if (lastStep?.step_type === 'reasoning' && lastStep.status === 'streaming') {
          lastStep.status = 'completed'
        }
        chatStore.updateMessageById(assistantMsgId, { content: `Error: ${data.content}`, agent_steps: [...agentSteps] })
        cleanup()
      })

      onEvent('chat.rate_limited', (data) => {
        chatStore.rateLimitRetryAfter = data.retry_after || 0
        chatStore.updateMessageById(assistantMsgId, { content: 'You\'ve reached your free tier limit. Please wait or add your own API key in Settings.' })
        cleanup()
      })

      // Collect ready dataset connection IDs from the dataset status composable
      const { datasets: currentDatasets } = useDatasetStatus()
      const readyConnectionIds = currentDatasets.value
        .filter(d => d.step === 'ready' && d.connectionId)
        .map(d => d.connectionId!)

      // Send via WebSocket
      ws.send({
        type: 'chat.send',
        request_id: requestId,
        thread_id: chatStore.currentThreadId || null,
        message,
        connection_ids: readyConnectionIds,
        file_ids: fileIds
      })
    })
  }

  const newChat = () => {
    chatStore.startNewChat()
  }

  return { sendMessage, newChat }
}
