<template>
  <div class="mb-6">
    <!-- User message: left-aligned chat bubble -->
    <div v-if="message.role === 'user'">
      <div class="inline-block bg-gray-900 text-white rounded-2xl px-4 py-2.5 max-w-[80%] whitespace-pre-wrap">
        {{ message.content }}
      </div>

      <!-- Attachments -->
      <div v-if="message.attachments && message.attachments.length > 0" class="mt-2 flex flex-wrap gap-2 max-w-[80%]">
        <template v-for="attachment in message.attachments" :key="attachment.file_id ?? attachment.name">
          <!-- Image thumbnail -->
          <div
            v-if="isImageType(attachment.type)"
            class="h-16 w-16 overflow-hidden rounded-lg border border-gray-200 bg-gray-100 flex-shrink-0"
          >
            <img
              v-if="attachment.preview_url"
              :src="attachment.preview_url"
              :alt="attachment.name"
              class="h-full w-full object-cover"
            />
            <div v-else class="flex h-full w-full items-center justify-center">
              <svg class="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
          </div>

          <!-- Document pill -->
          <div
            v-else
            class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-100 px-3 py-2 max-w-48"
          >
            <svg class="h-4 w-4 flex-shrink-0 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div class="min-w-0 flex-1">
              <p class="truncate text-xs font-medium text-gray-700">{{ attachment.name }}</p>
              <p class="text-xs text-gray-500">{{ formatAttachmentSize(attachment.size) }}</p>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Skill suggestion message -->
    <div v-else-if="message.source === 'skill_suggestion'" class="pr-4 md:pr-32">
      <div class="flex gap-2.5 items-start">
        <div class="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center flex-shrink-0">
          <span class="text-white text-xs">&starf;</span>
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-gray-900 mb-1 text-[13px]">I noticed some patterns in your conversations</div>
          <div class="text-gray-500 text-xs mb-3">
            Based on your recent activity, I have {{ pendingSuggestions.length }} skill suggestion{{ pendingSuggestions.length !== 1 ? 's' : '' }} that could save you time.
          </div>
          <TransitionGroup name="suggestion-list" tag="div" class="space-y-2">
            <ChatSkillSuggestionCard
              v-for="s in pendingSuggestions"
              :key="s.id"
              :suggestion="s"
              @accept="handleAcceptSuggestion"
              @dismiss="handleDismissSuggestion"
            />
          </TransitionGroup>
        </div>
      </div>
    </div>

    <!-- Assistant message: left-aligned plain text -->
    <div v-else class="pr-4 md:pr-32">
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

      <!-- Live steps log (collapses when final answer arrives) -->
      <div v-if="message.steps_log?.length" class="mt-1 font-mono text-[11px] text-gray-400 bg-gray-50/80 border border-gray-100 rounded-md px-3 py-2 leading-relaxed">
        <button
          @click="message.steps_log_expanded = !message.steps_log_expanded"
          class="flex items-center gap-1 cursor-pointer text-gray-400 hover:text-gray-500"
        >
          <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path v-if="!message.steps_log_expanded" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
          {{ message.steps_log.length }} steps
        </button>
        <div v-if="message.steps_log_expanded" class="mt-1.5 whitespace-pre-wrap">{{ message.steps_log.join('\n') }}
          <div v-if="chatStore.isStreaming" class="flex items-center gap-1 mt-1.5 pt-1.5 border-t border-gray-100">
            <span class="text-[10px] text-glow-orange">working...</span>
          </div>
        </div>
      </div>

      <!-- SQL Query (collapsible) -->
      <div v-if="message.sql" class="mt-3">
        <button
          @click="sqlExpanded = !sqlExpanded"
          class="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg
            class="w-3 h-3 transition-transform"
            :class="{ 'rotate-90': sqlExpanded }"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
          ><path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" /></svg>
          SQL Query
        </button>
        <div v-if="sqlExpanded" class="mt-1.5 rounded-lg bg-gray-50 p-4">
          <pre class="text-sm whitespace-pre-wrap"><code>{{ message.sql }}</code></pre>
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

      <!-- Agent steps / reasoning toggle (hidden when steps_log is present) -->
      <div v-if="hasSteps && !message.steps_log?.length" class="mt-3">
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

      <!-- User question: structured multi-question input (active or answered) -->
      <ChatUserQuestion
        v-if="(showActions || isQuestionAnswered) && actionType === 'user_question' && userQuestion"
        :questions="userQuestion"
        :answered="isQuestionAnswered"
        :answered-text="followingUserContent"
        @submit="emit('send-action', $event, 'qa_answer')"
      />

      <!-- Dashboard question: multi-select chips (active or answered) -->
      <ChatDashboardQuestion
        v-else-if="(showActions || isQuestionAnswered) && actionType === 'dashboard_question' && dashboardQuestion"
        :options="dashboardQuestion.options"
        :allow-multiple="dashboardQuestion.allowMultiple"
        :answered="isQuestionAnswered"
        :answered-text="followingUserContent"
        @submit="emit('send-action', $event, 'qa_answer')"
      />

      <!-- View Dashboard button (dashboard_created) -->
      <div v-else-if="showActions && actionType === 'dashboard_created'" class="mt-3">
        <button
          @click="viewDashboard"
          class="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:border-gray-300 hover:bg-gray-50 transition-colors"
        >
          <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          View Dashboard
          <svg class="h-3 w-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>

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
import type { SkillSuggestion } from '~/types/skillSuggestion'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  message: Message
  showActions?: boolean
  actionType?: 'soul' | 'dashboard' | 'dashboard_question' | 'dashboard_created' | 'user_question' | null
  followingUserContent?: string
}>()

const emit = defineEmits<{
  'send-action': [text: string, source?: Message['source']]
}>()

const chatStore = useChatStore()
const dashboardStore = useDashboardStore()
const api = useApi()
const sqlExpanded = ref(false)

const pendingSuggestions = computed(() =>
  (props.message.skillSuggestions ?? []).filter(s => chatStore.skillSuggestions.some(ss => ss.id === s.id))
)

const handleAcceptSuggestion = async (id: string) => {
  try {
    await api.skills.respondToSuggestion(id, 'accept')
  } catch { /* best-effort */ }
  chatStore.removeSkillSuggestion(id)
}

const handleDismissSuggestion = async (id: string) => {
  try {
    await api.skills.respondToSuggestion(id, 'dismiss')
  } catch { /* best-effort */ }
  chatStore.removeSkillSuggestion(id)
}

const hasSteps = computed(() =>
  props.message.role === 'assistant' &&
  props.message.source !== 'heartbeat' &&
  !!(props.message.agent_steps?.length || props.message.thinking_steps?.length)
)

const stepCount = computed(() =>
  props.message.agent_steps?.length || props.message.thinking_steps?.length || 0
)

const openReasoning = () => {
  chatStore.selectMessageForReasoning(props.message.id)
}

const isQuestionAnswered = computed(() => {
  if (props.actionType !== 'user_question' && props.actionType !== 'dashboard_question') return false
  return !props.showActions
})

const createdDashboardId = computed<number | null>(() => {
  for (const step of props.message.agent_steps ?? []) {
    if (step.tool_name !== 'create_dashboard' && step.tool_name !== 'update_dashboard') continue
    try {
      const result = typeof step.content?.result === 'string' ? JSON.parse(step.content.result) : step.content?.result
      if (result?.success === true) return result.dashboard_id ?? null
    } catch { continue }
  }
  return null
})

const viewDashboard = async () => {
  await navigateTo(createdDashboardId.value ? `/dashboard?id=${createdDashboardId.value}` : '/dashboard')
}

const IMAGE_MIME_TYPES = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp'])

const isImageType = (mimeType: string) => IMAGE_MIME_TYPES.has(mimeType)

const formatAttachmentSize = (bytes: number) => {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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

const userQuestion = computed(() => {
  const step = props.message.agent_steps?.find(s => s.tool_name === 'ask_user_question')
  if (!step) return null
  const result = step.content?.result
  if (result) {
    try {
      const parsed = typeof result === 'string' ? JSON.parse(result) : result
      if (parsed?.questions) return parsed.questions
    } catch {}
  }
  const args = step.content?.args
  if (!args?.questions) return null
  try {
    return typeof args.questions === 'string' ? JSON.parse(args.questions) : args.questions
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

.suggestion-list-leave-active {
  transition: all 0.3s ease;
}
.suggestion-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.suggestion-list-move {
  transition: transform 0.3s ease;
}
</style>
