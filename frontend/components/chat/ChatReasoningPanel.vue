<template>
  <div class="flex flex-col h-full bg-white overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
      <h2 class="text-sm font-medium text-gray-900">Reasoning</h2>
      <button
        @click="chatStore.closeReasoningPanel()"
        class="text-gray-400 hover:text-gray-600 transition-colors"
        aria-label="Close reasoning panel"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>

    <!-- Empty state -->
    <div v-if="!selectedMessage || !steps.length" class="flex flex-1 items-center justify-center px-6">
      <p class="text-sm text-gray-400 text-center">
        {{ chatStore.isStreaming ? 'Agent is working...' : 'Click an assistant message to see its reasoning.' }}
      </p>
    </div>

    <!-- Tree view -->
    <div v-else class="flex-1 overflow-y-auto px-4 py-4 font-mono text-xs">
      <!-- Root: Orchestrator -->
      <div class="flex items-center gap-1.5 py-0.5 mb-0.5">
        <span class="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />
        <span class="font-medium text-gray-800 font-sans">Orchestrator</span>
        <span v-if="rootTimestamp" class="ml-auto text-[10px] font-mono text-gray-400">{{ rootTimestamp }}</span>
      </div>

      <!-- Root's children -->
      <ChatReasoningTreeNode
        v-for="(child, idx) in treeNodes.children"
        :key="idx"
        :node="child"
        :is-last="idx === treeNodes.children.length - 1"
        :ancestors="[]"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentStep } from '~/stores/chat'

interface TreeNode {
  type: 'agent' | 'action' | 'result' | 'reasoning'
  label: string
  detail?: string
  status?: 'in-progress' | 'completed'
  duration?: string
  timestamp?: string
  children: TreeNode[]
}

const chatStore = useChatStore()

// Determine which message's steps to show
const selectedMessage = computed(() => {
  const id = chatStore.selectedMessageId
  if (id) return chatStore.messages.find(m => m.id === id) || null
  const msgs = chatStore.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i]
  }
  return null
})

const steps = computed((): AgentStep[] => selectedMessage.value?.agent_steps || [])

// --- Formatting helpers ---

const formatToolName = (name?: string): string => {
  if (!name) return 'Tool'
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

const formatTimestamp = (step: AgentStep): string => {
  const ts = step.started_at ?? (step.created_at ? new Date(step.created_at).getTime() : undefined)
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const getResultLabel = (result: any): string => {
  if (!result) return 'Completed'
  if (Array.isArray(result)) return `Found ${result.length} item${result.length !== 1 ? 's' : ''}`
  if (typeof result === 'object') {
    if ('row_count' in result) return `Completed: ${result.row_count} row${result.row_count !== 1 ? 's' : ''}`
    if ('rows' in result && Array.isArray(result.rows)) return `Completed: ${result.rows.length} row${result.rows.length !== 1 ? 's' : ''}`
  }
  return 'Completed'
}

const formatArgs = (args: Record<string, any> | undefined): string | undefined => {
  if (!args || Object.keys(args).length === 0) return undefined
  const entries = Object.entries(args).filter(([k]) => !k.startsWith('_'))
  if (entries.length === 0) return undefined
  return entries
    .map(([k, v]) => {
      const val = typeof v === 'string' ? v : JSON.stringify(v, null, 2)
      return `**${k}**: ${val}`
    })
    .join('\n\n')
}

// --- Tree transformation ---

const SUB_AGENT_TOOLS = new Set(['data_agent', 'rag_agent'])
const AGENT_LABELS: Record<string, string> = {
  data_agent: 'Data Agent',
  rag_agent: 'RAG Agent',
}

const rootTimestamp = computed((): string | undefined => {
  const first = steps.value[0]
  return first ? formatTimestamp(first) || undefined : undefined
})

const treeNodes = computed((): TreeNode => {
  const root: TreeNode = { type: 'agent', label: 'Orchestrator', children: [] }

  for (const step of steps.value) {
    // Handle reasoning steps
    if (step.step_type === 'reasoning') {
      root.children.push({
        type: 'reasoning',
        label: step.content?.text || 'Thinking...',
        status: 'completed',
        timestamp: formatTimestamp(step) || undefined,
        children: [],
      })
      continue
    }

    if (step.step_type !== 'tool_call') continue

    const ts = formatTimestamp(step) || undefined
    const dur = typeof step.duration_ms === 'number' ? formatDuration(step.duration_ms) : undefined
    const nodeStatus: 'in-progress' | 'completed' = step.status === 'completed' ? 'completed' : 'in-progress'
    const argsDetail = formatArgs(step.content?.args)

    if (SUB_AGENT_TOOLS.has(step.tool_name || '')) {
      const agentLabel = AGENT_LABELS[step.tool_name!] || formatToolName(step.tool_name)
      const agentNode: TreeNode = { type: 'agent', label: agentLabel, children: [] }

      // Sub-steps from content.sub_steps
      for (const subStep of (step.content?.sub_steps || [])) {
        let subTs: string | undefined
        if (subStep.started_at) {
          subTs = new Date(subStep.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        } else if (subStep.created_at) {
          subTs = new Date(subStep.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        }
        agentNode.children.push({
          type: 'action',
          label: formatToolName(subStep.tool_name),
          timestamp: subTs,
          status: subStep.status === 'completed' ? 'completed' : 'in-progress',
          children: [],
        })
      }

      // Result node when completed
      if (step.status === 'completed' && step.content?.result !== undefined) {
        agentNode.children.push({
          type: 'result',
          label: getResultLabel(step.content.result),
          status: 'completed',
          timestamp: ts,
          children: [],
        })
      }

      root.children.push({
        type: 'action',
        label: `Routing to ${agentLabel}`,
        detail: argsDetail,
        status: nodeStatus,
        duration: dur,
        timestamp: ts,
        children: [agentNode],
      })
    } else {
      // Direct orchestrator tool call
      root.children.push({
        type: 'action',
        label: formatToolName(step.tool_name),
        detail: argsDetail,
        status: nodeStatus,
        duration: dur,
        timestamp: ts,
        children: [],
      })
    }
  }

  // Synthetic "Response generated" node when streaming is done
  if (steps.value.length > 0 && !chatStore.isStreaming) {
    const lastStep = steps.value[steps.value.length - 1]
    root.children.push({
      type: 'result',
      label: 'Response generated',
      status: 'completed',
      timestamp: formatTimestamp(lastStep) || undefined,
      children: [],
    })
  }

  return root
})
</script>
