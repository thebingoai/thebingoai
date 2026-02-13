<template>
  <div class="flex flex-1 flex-col">
    <ChatThread />
    <ChatInputBar @send="handleSend" />
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
