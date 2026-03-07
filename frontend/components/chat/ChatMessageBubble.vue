<template>
  <div class="mb-6">
    <!-- User message: left-aligned chat bubble -->
    <div v-if="message.role === 'user'">
      <div class="inline-block bg-gray-900 text-white rounded-2xl px-4 py-2.5 max-w-[80%] whitespace-pre-wrap">
        {{ message.content }}
      </div>
    </div>

    <!-- Assistant message: left-aligned plain text -->
    <div v-else class="pr-32">
      <!-- Heartbeat source label -->
      <div v-if="message.source === 'heartbeat'" class="mb-1.5 flex items-center gap-1.5">
        <span class="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Scheduled
        </span>
      </div>

      <!-- Typing indicator when assistant message is empty during streaming -->
      <div v-if="!message.content && chatStore.isStreaming" class="typing-indicator">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>

      <!-- Assistant message with markdown -->
      <UiMarkdownRenderer v-else :content="message.content" />

      <!-- SQL Query -->
      <div v-if="message.sql" class="mt-3">
        <div class="rounded-lg bg-gray-50 p-4">
          <pre class="text-sm"><code>{{ message.sql }}</code></pre>
        </div>
      </div>

      <!-- Results Table -->
      <div v-if="message.results && message.results.length > 0" class="mt-3 overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg">
          <thead class="bg-gray-50">
            <tr>
              <th
                v-for="(value, key) in message.results[0]"
                :key="key"
                class="px-4 py-2 text-left text-xs font-normal text-gray-700"
              >
                {{ key }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-200 bg-white">
            <tr v-for="(row, idx) in message.results.slice(0, 50)" :key="idx">
              <td
                v-for="(value, key) in row"
                :key="key"
                class="px-4 py-2 text-sm text-gray-900"
              >
                {{ value }}
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="message.results.length > 50" class="mt-2 text-sm text-gray-500">
          Showing 50 of {{ message.results.length }} rows
        </p>
      </div>

      <!-- Agent steps / reasoning toggle -->
      <div v-if="hasSteps" class="mt-3">
        <button
          @click="openReasoning"
          class="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.15A4.98 4.98 0 0112 17a4.98 4.98 0 01-2.39-.606l-.347-.15z" />
          </svg>
          <span>{{ stepCount }} reasoning step{{ stepCount !== 1 ? 's' : '' }}</span>
        </button>
      </div>

      <!-- Dashboard question: multi-select chips -->
      <ChatDashboardQuestion
        v-if="showActions && actionType === 'dashboard_question' && dashboardQuestion"
        :options="dashboardQuestion.options"
        :allow-multiple="dashboardQuestion.allowMultiple"
        @submit="emit('send-action', $event)"
      />

      <!-- Proposal action buttons (soul / dashboard plan) -->
      <div v-else-if="showActions" class="mt-3 flex items-center gap-2">
        <UiButton size="sm" variant="primary" @click="emit('send-action', 'yes')">
          {{ actionType === 'dashboard' ? 'Approve plan' : 'Yes, apply' }}
        </UiButton>
        <UiButton size="sm" variant="outline" @click="emit('send-action', 'no')">
          {{ actionType === 'dashboard' ? 'Revise' : 'No thanks' }}
        </UiButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Message } from '~/stores/chat'

const props = defineProps<{
  message: Message
  showActions?: boolean
  actionType?: 'soul' | 'dashboard' | 'dashboard_question' | null
}>()

const emit = defineEmits<{
  'send-action': [text: string]
}>()

const chatStore = useChatStore()

const hasSteps = computed(() =>
  props.message.role === 'assistant' &&
  props.message.source !== 'heartbeat' &&
  !!(props.message.agent_steps?.length || props.message.thinking_steps?.length)
)

const stepCount = computed(() =>
  props.message.agent_steps?.length || props.message.thinking_steps?.length || 0
)

const openReasoning = () => {
  chatStore.openReasoningPanel(props.message.id)
}

const dashboardQuestion = computed(() => {
  const step = props.message.agent_steps?.find(s => s.tool_name === 'ask_dashboard_question')
  if (!step) return null
  // Try to get from tool result first, then args
  const result = step.content?.result
  if (result) {
    try {
      const parsed = typeof result === 'string' ? JSON.parse(result) : result
      if (parsed?.options) return { options: parsed.options, allowMultiple: parsed.allow_multiple !== false }
    } catch {}
  }
  const args = step.content?.args
  if (!args?.options) return null
  try {
    const options = typeof args.options === 'string' ? JSON.parse(args.options) : args.options
    return { options, allowMultiple: args.allow_multiple !== false }
  } catch {
    return null
  }
})
</script>

<style scoped>
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #9ca3af;
  animation: typing-bounce 1.4s infinite ease-in-out;
}

.typing-dot:nth-child(1) {
  animation-delay: 0s;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.7;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}
</style>
