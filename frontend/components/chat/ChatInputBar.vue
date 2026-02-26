<template>
  <div class="border-t border-gray-200 bg-white px-24 py-4">
    <form @submit.prevent="handleSubmit" class="flex items-end gap-2">
      <div class="flex-1">
        <textarea
          ref="textareaRef"
          v-model="chatStore.inputText"
          placeholder="Ask a question about your data..."
          rows="1"
          class="w-full resize-none rounded-lg border border-gray-300 px-4 py-2.5 max-h-48 overflow-y-auto"
          :disabled="chatStore.isStreaming"
          @input="autoResize"
          @keydown="handleKeydown"
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

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

const isInsideCodeBlock = (text: string, cursorPos: number): boolean => {
  const textBeforeCursor = text.slice(0, cursorPos)
  const fenceCount = (textBeforeCursor.match(/```/g) || []).length
  return fenceCount % 2 !== 0
}

const insertNewline = (el: HTMLTextAreaElement) => {
  const start = el.selectionStart
  const end = el.selectionEnd
  chatStore.inputText = el.value.slice(0, start) + '\n' + el.value.slice(end)
  nextTick(() => {
    el.selectionStart = el.selectionEnd = start + 1
    autoResize()
  })
}

const handleKeydown = (event: KeyboardEvent) => {
  const el = textareaRef.value
  if (!el || event.key !== 'Enter') return

  if (event.shiftKey || isInsideCodeBlock(el.value, el.selectionStart)) {
    event.preventDefault()
    insertNewline(el)
  } else {
    event.preventDefault()
    handleSubmit()
  }
}

const handleSubmit = () => {
  if (chatStore.inputText.trim() && !chatStore.isStreaming) {
    emit('send')
  }
}

watch(() => chatStore.inputText, (newVal) => {
  if (!newVal) {
    nextTick(() => {
      const el = textareaRef.value
      if (el) el.style.height = 'auto'
    })
  }
})
</script>
