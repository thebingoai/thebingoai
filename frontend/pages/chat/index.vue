<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main chat area -->
    <div class="flex flex-1 flex-col min-w-0 min-h-0">
      <ChatThread @send-action="handleAction" />
      <ChatInputBar @send="handleSend" @reset="handleReset" />
    </div>
    <!-- Conversation info panel (slides in from the right) -->
    <div
      class="shrink-0 overflow-hidden transition-all duration-300 ease-in-out"
      :class="chatStore.infoPanelOpen ? 'w-80 border-l border-gray-200' : 'w-0'"
    >
      <ConversationInfoPanel v-if="chatStore.infoPanelOpen" class="w-80" />
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()
const chat = useChat()
const { getFileIds, clearFiles } = useChatFileUpload()

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
