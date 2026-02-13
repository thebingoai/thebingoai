<template>
  <div ref="threadRef" class="flex-1 overflow-y-auto p-6">
    <div v-if="chatStore.messages.length === 0" class="flex h-full items-center justify-center">
      <div class="text-center">
        <h2 class="text-2xl font-bold text-gray-900 mb-2">Ask me anything about your data</h2>
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
</template>

<script setup lang="ts">
const chatStore = useChatStore()
const threadRef = ref<HTMLElement>()

// Auto-scroll to bottom when new message arrives
watch(() => chatStore.messages.length, () => {
  nextTick(() => {
    if (threadRef.value) {
      threadRef.value.scrollTop = threadRef.value.scrollHeight
    }
  })
})
</script>
