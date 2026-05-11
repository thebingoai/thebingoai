<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main chat area -->
    <div class="flex flex-1 flex-col min-w-0 min-h-0">
      <ChatThread @send-action="handleAction" />
      <ChatInputBar @send="handleSend" @reset="handleReset" />
    </div>

    <!-- Desktop: Conversation info panel (slides in from the right) -->
    <div
      v-if="!isMobile"
      class="shrink-0 overflow-hidden transition-all duration-300 ease-in-out"
      :class="chatStore.infoPanelOpen ? 'w-[440px] border-l border-gray-200 dark:border-neutral-700' : 'w-0'"
    >
      <ConversationInfoPanel v-if="chatStore.infoPanelOpen" class="w-[440px]" />
    </div>

    <!-- Mobile: Info panel as full-screen overlay -->
    <Transition name="slide-up">
      <div
        v-if="isMobile && chatStore.infoPanelOpen"
        class="fixed inset-0 z-50 bg-white dark:bg-neutral-900 flex flex-col"
      >
        <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-neutral-700">
          <span class="text-sm font-medium text-gray-900 dark:text-white">Conversation Info</span>
          <button @click="chatStore.toggleInfoPanel()" class="p-1 rounded hover:bg-gray-100 dark:hover:bg-neutral-800">
            <X class="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <div class="flex-1 overflow-y-auto">
          <ConversationInfoPanel />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'

const chatStore = useChatStore()
const chat = useChat()
const { getFileIds, clearFiles } = useChatFileUpload()
const { isMobile } = useIsMobile()

// On mobile, default info panel to closed
onMounted(() => {
  if (isMobile.value) {
    chatStore.infoPanelOpen = false
  }
})

const handleSend = () => {
  if (chatStore.inputText.trim()) {
    const fileIds = getFileIds()
    chat.sendMessage(chatStore.inputText, fileIds)
    clearFiles()
  }
}

const handleAction = (text: string, source?: string) => {
  if (!chatStore.isStreaming) {
    chat.sendMessage(text, [], source ? { source: source as any } : undefined)
  }
}

const handleReset = () => {
  chat.resetContext()
}

definePageMeta({
  middleware: 'auth'
})
</script>
