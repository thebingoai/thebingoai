<template>
  <div class="border-t border-gray-200 bg-white px-24 py-4">
    <form @submit.prevent="handleSubmit" class="rounded-xl border border-gray-300 flex flex-col focus-within:border-gray-400 transition-colors">
      <textarea
        ref="textareaRef"
        v-model="chatStore.inputText"
        placeholder="Ask a question about your data..."
        rows="1"
        class="w-full resize-none px-4 pt-3 pb-2 max-h-48 overflow-y-auto bg-transparent outline-none rounded-t-xl"
        :disabled="chatStore.isStreaming"
        @input="autoResize"
        @keydown="handleKeydown"
      />
      <div class="flex justify-end gap-1.5 px-3 pb-3">
        <!-- New Topic button — only visible on permanent conversation -->
        <button
          v-if="isPermanentConversation"
          type="button"
          :disabled="chatStore.isStreaming"
          @click="emit('reset')"
          title="New Topic"
          class="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 disabled:opacity-40 transition-colors"
        >
          <Scissors class="h-4 w-4" />
        </button>
        <!-- Send button -->
        <button
          type="submit"
          :disabled="!chatStore.inputText.trim() || chatStore.isStreaming"
          class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-900 text-white disabled:opacity-40 hover:bg-gray-700 transition-colors"
        >
          <ArrowUp class="h-4 w-4" />
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { Scissors, ArrowUp } from 'lucide-vue-next'

const chatStore = useChatStore()
const emit = defineEmits<{
  send: []
  reset: []
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const isPermanentConversation = computed(() => chatStore.currentConversation?.type === 'permanent')

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
