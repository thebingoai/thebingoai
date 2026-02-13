<template>
  <div class="border-t border-gray-200 bg-white p-4">
    <form @submit.prevent="handleSubmit" class="flex items-end gap-2">
      <div class="flex-1">
        <textarea
          v-model="chatStore.inputText"
          placeholder="Ask a question about your data..."
          rows="1"
          class="w-full resize-none rounded-lg border border-gray-300 px-4 py-2 focus-ring"
          :disabled="chatStore.isStreaming"
          @keydown.enter.exact.prevent="handleSubmit"
        />
      </div>
      <UiButton
        type="submit"
        :disabled="!chatStore.inputText.trim() || chatStore.isStreaming"
        :loading="chatStore.isStreaming"
      >
        Send
      </UiButton>
    </form>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()
const emit = defineEmits<{
  send: []
}>()

const handleSubmit = () => {
  if (chatStore.inputText.trim() && !chatStore.isStreaming) {
    emit('send')
  }
}
</script>
