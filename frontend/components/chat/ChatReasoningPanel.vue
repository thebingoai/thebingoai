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

    <!-- Steps list -->
    <div v-else class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
      <div
        v-for="(step, idx) in steps"
        :key="idx"
      >
        <!-- tool_call step -->
        <div v-if="step.step_type === 'tool_call'" class="rounded-lg border border-gray-100 bg-gray-50 overflow-hidden">
          <div class="flex items-center gap-2 px-3 py-2 bg-gray-100">
            <!-- Status dot -->
            <span
              class="w-2 h-2 rounded-full shrink-0"
              :class="step.status === 'completed' ? 'bg-green-400' : 'bg-amber-400 animate-pulse'"
            />
            <span class="text-xs font-medium text-gray-700 truncate">{{ formatToolName(step.tool_name) }}</span>
            <span class="ml-auto text-xs text-gray-400">{{ agentLabel(step.agent_type) }}</span>
          </div>

          <!-- Args -->
          <div v-if="hasContent(step.content?.args)" class="px-3 py-2 border-t border-gray-100">
            <div class="text-xs text-gray-500 mb-1">Input</div>
            <div v-if="step.content.args?.question" class="text-xs text-gray-700 italic">
              "{{ step.content.args.question }}"
            </div>
            <div v-else-if="step.content.args?.sql" class="rounded bg-white border border-gray-200 p-2 mt-1">
              <pre class="text-xs text-gray-800 whitespace-pre-wrap break-all">{{ step.content.args.sql }}</pre>
            </div>
            <div v-else class="text-xs text-gray-600 font-mono break-all">
              {{ JSON.stringify(step.content.args, null, 2) }}
            </div>
          </div>

          <!-- Result summary (collapsed into tool_call for cleaner UI) -->
          <div v-if="step.status === 'completed' && hasContent(step.content?.result)" class="px-3 py-2 border-t border-gray-100">
            <div class="text-xs text-gray-500 mb-1">Result</div>
            <ChatReasoningResultSummary :result="step.content.result" :tool-name="step.tool_name" />
          </div>

          <!-- Data agent sub-steps -->
          <div v-if="step.content?.sub_steps?.length" class="border-t border-gray-100">
            <div class="px-3 py-1.5 bg-gray-50">
              <button
                @click="toggleSubSteps(idx)"
                class="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
              >
                <span>{{ expandedSubSteps.has(idx) ? '▼' : '▸' }}</span>
                <span>{{ step.content.sub_steps.length }} internal steps</span>
              </button>
            </div>
            <div v-if="expandedSubSteps.has(idx)" class="px-3 py-2 space-y-2">
              <div
                v-for="(subStep, subIdx) in step.content.sub_steps"
                :key="subIdx"
                class="rounded border border-gray-100 bg-white overflow-hidden"
              >
                <div class="flex items-center gap-2 px-2 py-1.5 bg-gray-50">
                  <span class="w-1.5 h-1.5 rounded-full bg-gray-400 shrink-0" />
                  <span class="text-xs font-medium text-gray-600">{{ formatToolName(subStep.tool_name) }}</span>
                </div>
                <div v-if="hasContent(subStep.content?.args)" class="px-2 py-1.5">
                  <div v-if="subStep.content?.args?.sql" class="rounded bg-gray-50 p-1.5">
                    <pre class="text-xs text-gray-700 whitespace-pre-wrap break-all">{{ subStep.content.args.sql }}</pre>
                  </div>
                  <div v-else class="text-xs text-gray-600 font-mono break-all">
                    {{ JSON.stringify(subStep.content.args) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- tool_result step (standalone — only shown if not merged into tool_call above) -->
        <div
          v-else-if="step.step_type === 'tool_result' && !isResultMerged(idx)"
          class="rounded-lg border border-gray-100 bg-white px-3 py-2"
        >
          <div class="text-xs text-gray-500 mb-1">{{ formatToolName(step.tool_name) }} result</div>
          <ChatReasoningResultSummary :result="step.content?.result" :tool-name="step.tool_name" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AgentStep } from '~/stores/chat'

const chatStore = useChatStore()

// Determine which message's steps to show
const selectedMessage = computed(() => {
  const id = chatStore.selectedMessageId
  if (id) return chatStore.messages.find(m => m.id === id) || null
  // Fall back to latest assistant message
  const msgs = chatStore.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') return msgs[i]
  }
  return null
})

const steps = computed((): AgentStep[] => selectedMessage.value?.agent_steps || [])

// Sub-step expansion tracking
const expandedSubSteps = ref(new Set<number>())
const toggleSubSteps = (idx: number) => {
  if (expandedSubSteps.value.has(idx)) {
    expandedSubSteps.value.delete(idx)
  } else {
    expandedSubSteps.value.add(idx)
  }
}

// When a new message is selected, reset sub-step expansion
watch(() => chatStore.selectedMessageId, () => {
  expandedSubSteps.value.clear()
})

// A tool_result is "merged" if the preceding tool_call already shows the result inline
const isResultMerged = (idx: number): boolean => {
  const step = steps.value[idx]
  if (idx === 0) return false
  const prev = steps.value[idx - 1]
  return (
    prev.step_type === 'tool_call' &&
    prev.tool_name === step.tool_name &&
    prev.status === 'completed'
  )
}

const hasContent = (val: any): boolean => {
  if (!val) return false
  if (typeof val === 'object') return Object.keys(val).length > 0
  return Boolean(val)
}

const formatToolName = (name?: string): string => {
  if (!name) return 'Tool'
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

const agentLabel = (agentType: string): string => {
  const labels: Record<string, string> = {
    orchestrator: 'Orchestrator',
    data_agent: 'Data Agent',
    rag_agent: 'RAG Agent'
  }
  return labels[agentType] || agentType
}
</script>
