<template>
  <div class="relative flex-1 flex flex-col min-h-0">
    <!-- Header bar — full-width white background keeps scroll content below the toggle button -->
    <div class="flex-shrink-0 flex items-center h-16 bg-white pl-14 pr-4 pt-1">
      <div v-if="chatStore.currentThreadId" class="flex w-full items-center pointer-events-none">
        <input
          v-if="isEditingTitle"
          ref="titleInput"
          v-model="editTitle"
          @blur="saveTitle"
          @keydown.enter="saveTitle"
          @keydown.escape="cancelEdit"
          class="w-full pointer-events-auto text-sm text-gray-700 bg-transparent border-b border-gray-300 outline-none w-48 "
        />
        <span
          v-else
          @click="startEditTitle"
          class="pointer-events-auto text-sm text-gray-700 cursor-pointer hover:text-gray-900 transition-colors"
        >
          {{ currentTitle }}
        </span>
      </div>
    </div>

    <!-- Scrollable message content -->
    <div ref="threadRef" class="flex-1 overflow-y-auto pl-24 pt-6 pb-36">
      <div v-if="chatStore.messages.length === 0" class="flex h-full items-center justify-center">
        <div v-if="chatStore.currentConversation?.type === 'permanent'" class="text-center max-w-sm">
          <h2 class="text-2xl font-medium text-gray-900 mb-2">Welcome to {{ chatStore.permanentConversation?.title || 'Bingo AI' }}</h2>
          <p class="text-gray-500 mb-4">I'm your personal assistant — you can give me a name, set my personality, and teach me how you like to work.</p>
          <p class="text-gray-400 text-sm">For one-off data queries, use <span class="font-medium text-gray-500">New Task</span>.</p>
        </div>
        <div v-else class="text-center">
          <h2 class="text-2xl font-medium text-gray-900 mb-2">Ask me anything about your data</h2>
          <p class="text-gray-500">I can write SQL queries and analyze your database</p>
        </div>
      </div>
      <div v-else>
        <template v-for="(message, index) in chatStore.messages" :key="message.id">
          <!-- Date header (shown when date changes between messages) -->
          <div
            v-if="message.source !== 'context_reset' && getDateLabel(message, index)"
            class="flex items-center gap-3 my-4 pr-32"
          >
            <div class="flex-1 border-t border-gray-100" />
            <span class="text-xs text-gray-400">{{ getDateLabel(message, index) }}</span>
            <div class="flex-1 border-t border-gray-100" />
          </div>

          <!-- Context reset divider -->
          <div v-if="message.source === 'context_reset'" class="flex items-center gap-3 my-6 pr-32">
            <div class="flex-1 border-t border-gray-200" />
            <span class="text-xs text-gray-400 whitespace-nowrap">New Topic</span>
            <div class="flex-1 border-t border-gray-200" />
          </div>

          <!-- Regular message bubble -->
          <ChatMessageBubble
            v-else
            :message="message"
            :show-actions="shouldShowActions(message, index)"
            :action-type="getActionType(message)"
            @send-action="emit('send-action', $event)"
          />
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatDateLabel, isSameDay } from '~/utils/format'
import type { Message } from '~/stores/chat'

const emit = defineEmits<{
  'send-action': [text: string]
}>()

const chatStore = useChatStore()
const chat = useChat()

const shouldShowActions = (message: Message, index: number): boolean => {
  if (message.role !== 'assistant') return false
  if (chatStore.isStreaming && index === chatStore.messages.length - 1) return false
  // Dashboard created: always show (navigation link, not a one-time action)
  const hasDashboardCreated = message.agent_steps?.some(step => {
    if (step.tool_name !== 'create_dashboard') return false
    try {
      const result = typeof step.content?.result === 'string' ? JSON.parse(step.content.result) : step.content?.result
      return result?.success === true
    } catch { return false }
  })
  if (hasDashboardCreated) return true
  const hasProposal = message.agent_steps?.some(
    step => step.tool_name === 'propose_soul_update' || step.tool_name === 'propose_dashboard_plan' || step.tool_name === 'ask_dashboard_question'
  )
  if (!hasProposal) return false
  return !chatStore.messages.slice(index + 1).some(m => m.role === 'user')
}

const getActionType = (message: Message): 'soul' | 'dashboard' | 'dashboard_question' | 'dashboard_created' | null => {
  if (message.agent_steps?.some(s => s.tool_name === 'ask_dashboard_question')) return 'dashboard_question'
  if (message.agent_steps?.some(s => s.tool_name === 'propose_dashboard_plan')) return 'dashboard'
  if (message.agent_steps?.some(s => s.tool_name === 'propose_soul_update')) return 'soul'
  const hasDashboardCreatedAction = message.agent_steps?.some(step => {
    if (step.tool_name !== 'create_dashboard') return false
    try {
      const result = typeof step.content?.result === 'string' ? JSON.parse(step.content.result) : step.content?.result
      return result?.success === true
    } catch { return false }
  })
  if (hasDashboardCreatedAction) return 'dashboard_created'
  return null
}

const threadRef = ref<HTMLElement>()
const titleInput = ref<HTMLInputElement>()
const isEditingTitle = ref(false)
const editTitle = ref('')

const currentTitle = computed(() => chatStore.currentConversation?.title || 'Untitled')

const startEditTitle = () => {
  editTitle.value = currentTitle.value
  isEditingTitle.value = true
  nextTick(() => {
    titleInput.value?.focus()
    titleInput.value?.select()
  })
}

const saveTitle = async () => {
  if (!isEditingTitle.value) return
  isEditingTitle.value = false
  const newTitle = editTitle.value.trim()
  if (newTitle && newTitle !== currentTitle.value && chatStore.currentThreadId) {
    try {
      await chat.renameConversation(chatStore.currentThreadId, newTitle)
    } catch (e) {
      console.error('Failed to rename conversation:', e)
    }
  }
}

const cancelEdit = () => {
  isEditingTitle.value = false
}

// Returns the date label to show above a message, or null if no label needed
const getDateLabel = (message: Message, index: number): string | null => {
  const messageDate = new Date(message.created_at)
  if (index === 0) return formatDateLabel(messageDate)
  // Find the previous non-context-reset message's date
  for (let i = index - 1; i >= 0; i--) {
    const prev = chatStore.messages[i]
    if (prev.source !== 'context_reset') {
      return isSameDay(messageDate, new Date(prev.created_at)) ? null : formatDateLabel(messageDate)
    }
  }
  return formatDateLabel(messageDate)
}

// Scroll function
const scrollToBottom = () => {
  if (threadRef.value) {
    threadRef.value.scrollTop = threadRef.value.scrollHeight
  }
}

// Scroll to bottom on initial mount (handles pre-existing messages)
onMounted(() => {
  nextTick(() => scrollToBottom())
})

// Throttled scroll for streaming content updates (leading + trailing edge)
let scrollThrottleTimer: NodeJS.Timeout | null = null
let pendingScroll = false
const throttledScroll = () => {
  if (!scrollThrottleTimer) {
    scrollToBottom()
    scrollThrottleTimer = setTimeout(() => {
      scrollThrottleTimer = null
      if (pendingScroll) {
        pendingScroll = false
        scrollToBottom()
      }
    }, 100)
  } else {
    pendingScroll = true
  }
}

// Auto-scroll to bottom when new message arrives (immediate)
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    scrollToBottom()
  })
})

// Auto-scroll during streaming content updates and tool step additions (throttled)
watch(
  () => {
    const lastMessage = chatStore.messages[chatStore.messages.length - 1]
    return (lastMessage?.content || '') + (lastMessage?.agent_steps?.length || 0)
  },
  () => {
    if (chatStore.isStreaming) {
      nextTick(() => {
        throttledScroll()
      })
    }
  }
)

// Scroll once more when streaming ends to catch the final word-buffer flush
watch(() => chatStore.isStreaming, (streaming, wasStreaming) => {
  if (wasStreaming && !streaming) {
    nextTick(() => scrollToBottom())
  }
})
</script>
