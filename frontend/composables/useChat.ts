import { useChatStore } from '~/stores/chat'
import type { Message, AgentStep } from '~/stores/chat'

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

    // Add empty assistant message placeholder
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      thinking_steps: [],
      agent_steps: [],
      created_at: new Date().toISOString()
    }
    chatStore.addMessage(assistantMessage)

    // Accumulate streaming content
    let accumulatedContent = ''
    let wordBuffer = ''
    const thinkingSteps: Array<{ step: string; description: string }> = []
    const agentSteps: AgentStep[] = []

    try {
      await api.chat.streamChat(
        message,
        chatStore.currentThreadId || undefined,
        {
          onToken: (content: string) => {
            wordBuffer += content
            accumulatedContent += content

            // Check if we have a complete word (space, punctuation, or newline)
            const hasCompleteWord = /[\s\n.,!?;:]/.test(content)

            if (hasCompleteWord) {
              // Update UI with accumulated content
              chatStore.updateLastMessage({ content: accumulatedContent })
              wordBuffer = ''
            }
          },
          onToolCall: (data: any) => {
            const toolName = data.content?.tool || data.tool || 'Tool'
            const args = data.content?.args || {}

            // Rich agent step
            const step: AgentStep = {
              agent_type: 'orchestrator',
              step_type: 'tool_call',
              tool_name: toolName,
              content: { args },
              status: 'started',
              started_at: Date.now()
            }
            agentSteps.push(step)

            // Legacy thinking step for backward compat
            thinkingSteps.push({ step: toolName, description: 'Running...' })
            chatStore.updateLastMessage({
              thinking_steps: [...thinkingSteps],
              agent_steps: [...agentSteps]
            })
          },
          onToolResult: (data: any) => {
            const toolName = data.content?.tool || data.tool || 'Tool'
            const result = data.content?.result || {}
            const serverDuration = data.content?.duration_ms

            // Find the most recent started tool_call step for this tool and mark it completed
            const lastPendingIdx = [...agentSteps].reverse().findIndex(
              s => s.step_type === 'tool_call' && s.status === 'started' && s.tool_name === toolName
            )
            if (lastPendingIdx !== -1) {
              const realIdx = agentSteps.length - 1 - lastPendingIdx
              const step = agentSteps[realIdx]
              step.status = 'completed'
              step.content.result = result
              // Prefer server-provided duration, fall back to client-side calculation
              step.duration_ms = serverDuration ?? (step.started_at ? Date.now() - step.started_at : undefined)
              // Attach data agent sub-steps if present
              if (result?.steps) {
                step.content.sub_steps = result.steps
              }
            }

            // Legacy thinking step update
            if (thinkingSteps.length > 0) {
              thinkingSteps[thinkingSteps.length - 1].description = 'Completed'
            }
            chatStore.updateLastMessage({
              thinking_steps: [...thinkingSteps],
              agent_steps: [...agentSteps]
            })
          },
          onStatus: (status: string) => {
            console.log('Status:', status)
          },
          onDone: (data: any) => {
            // Flush any remaining content in the word buffer
            if (wordBuffer) {
              chatStore.updateLastMessage({ content: accumulatedContent })
              wordBuffer = ''
            }

            // Update thread ID if new
            if (data.thread_id && !chatStore.currentThreadId) {
              chatStore.setCurrentThread(data.thread_id)
              chatStore.addConversation({
                id: data.thread_id,
                title: 'Untitled',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                message_count: 2
              })
            }
          },
          onTitle: (title: string) => {
            if (chatStore.currentThreadId) {
              chatStore.updateConversationTitle(chatStore.currentThreadId, title)
            }
          },
          onError: (error: string) => {
            chatStore.updateLastMessage({
              content: `Error: ${error}`
            })
          }
        }
      )
    } catch (error: any) {
      console.error('Chat error:', error)
      chatStore.updateLastMessage({
        content: 'Sorry, I encountered an error. Please try again.'
      })
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
      const messages: Message[] = (conversation.messages || []).map((msg: any, index: number) => ({
        id: msg.id ? String(msg.id) : `${threadId}-${index}`,
        role: msg.role,
        content: msg.content,
        created_at: msg.timestamp,
        agent_steps: [],
        thinking_steps: []
      }))
      chatStore.setMessages(messages)
      chatStore.setCurrentThread(threadId)

      // Load agent steps for assistant messages
      for (const msg of messages) {
        if (msg.role === 'assistant' && msg.id && !msg.id.includes('-')) {
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
    } catch (error) {
      console.error('Failed to load messages:', error)
    }
  }

  const renameConversation = async (threadId: string, title: string) => {
    await api.chat.updateTitle(threadId, title)
    chatStore.updateConversationTitle(threadId, title)
  }

  return {
    sendMessage,
    newChat,
    loadConversations,
    loadMessages,
    renameConversation
  }
}
