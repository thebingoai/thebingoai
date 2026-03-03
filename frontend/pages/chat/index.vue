<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main chat area -->
    <div class="flex flex-1 flex-col min-w-0 min-h-0">
      <ChatThread />
      <ChatInputBar @send="handleSend" @reset="handleReset" />
    </div>
    <!-- Reasoning panel (slides in from the right) -->
    <div
      class="shrink-0 overflow-hidden transition-all duration-300 ease-in-out"
      :class="chatStore.reasoningPanelOpen ? 'w-96 border-l border-gray-200' : 'w-0'"
    >
      <ChatReasoningPanel v-if="chatStore.reasoningPanelOpen" class="w-96" />
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()
const chat = useChat()

const handleSend = () => {
  if (chatStore.inputText.trim()) {
    chat.sendMessage(chatStore.inputText)
  }
}

const handleReset = () => {
  chat.resetContext()
}

definePageMeta({
  middleware: 'auth'
})
</script>
