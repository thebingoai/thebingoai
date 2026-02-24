<template>
  <div class="relative flex-1 flex flex-col min-h-0">
    <!-- Title overlay — aligned with toggle button at top-3 -->
    <div v-if="chatStore.currentThreadId" class="absolute top-3 left-0 right-0 z-10 text-center pointer-events-none">
      <input
        v-if="isEditingTitle"
        ref="titleInput"
        v-model="editTitle"
        @blur="saveTitle"
        @keydown.enter="saveTitle"
        @keydown.escape="cancelEdit"
        class="pointer-events-auto text-center text-sm text-gray-500 bg-transparent border-b border-gray-300 outline-none w-64"
      />
      <span
        v-else
        @click="startEditTitle"
        class="pointer-events-auto text-sm text-gray-400 cursor-pointer hover:text-gray-600 transition-colors"
      >
        {{ currentTitle }}
      </span>
    </div>

    <!-- Scrollable message content -->
    <div ref="threadRef" class="flex-1 overflow-y-auto px-24 py-6 pt-20">
      <div v-if="chatStore.messages.length === 0" class="flex h-full items-center justify-center">
        <div class="text-center">
          <h2 class="text-2xl font-medium text-gray-900 mb-2">Ask me anything about your data</h2>
          <p class="text-gray-500">I can write SQL queries and analyze your database</p>
        </div>
      </div>
      <div v-else>
        <ChatMessageBubble
          v-for="message in chatStore.messages"
          :key="message.id"
          :message="message"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()
const chat = useChat()
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

// Scroll function
const scrollToBottom = () => {
  if (threadRef.value) {
    threadRef.value.scrollTop = threadRef.value.scrollHeight
  }
}

// Throttled scroll for streaming content updates (leading-edge: scrolls immediately on first trigger)
let scrollThrottleTimer: NodeJS.Timeout | null = null
const throttledScroll = () => {
  if (!scrollThrottleTimer) {
    scrollToBottom()
    scrollThrottleTimer = setTimeout(() => {
      scrollThrottleTimer = null
    }, 100)
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
</script>
