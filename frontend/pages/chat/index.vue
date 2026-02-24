<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main chat area -->
    <div class="flex flex-1 flex-col min-w-0">
      <ChatThread />
      <ChatInputBar @send="handleSend" />
    </div>
    <!-- Reasoning panel (slides in from the right) -->
    <ChatReasoningPanel
      v-if="chatStore.reasoningPanelOpen"
      class="w-96 shrink-0 border-l border-gray-200"
    />
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

definePageMeta({
  middleware: 'auth'
})
</script>
