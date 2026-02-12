<template>
  <div class="border-t border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
    <div class="mb-3 flex items-center gap-2">
      <UiSelect
        v-model="chatStore.selectedNamespace"
        :options="namespaceOptions"
        size="sm"
        class="w-40"
      />
      <UiSelect
        v-model="chatStore.selectedProvider"
        :options="providerOptions"
        size="sm"
        class="w-32"
      />
      <div class="flex items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
        <span>Temp:</span>
        <input
          v-model.number="chatStore.temperature"
          type="range"
          min="0"
          max="2"
          step="0.1"
          class="w-20"
        />
        <span class="w-8 text-right">{{ chatStore.temperature.toFixed(1) }}</span>
      </div>
    </div>

    <div class="relative">
      <textarea
        v-model="chatStore.inputText"
        :disabled="disabled"
        placeholder="Ask a question..."
        rows="3"
        class="w-full resize-none rounded-lg border border-neutral-300 bg-white px-4 py-3 pr-24 transition-colors focus-ring disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-100"
        @keydown.enter.exact.prevent="handleSend"
        @keydown.enter.shift.exact="handleNewline"
      />

      <div class="absolute bottom-3 right-3 flex items-center gap-2">
        <UiButton
          size="sm"
          :disabled="!canSend"
          @click="handleSend"
        >
          <component :is="Send" class="h-4 w-4" />
          Send
        </UiButton>
      </div>
    </div>

    <p class="mt-2 text-xs text-neutral-500 dark:text-neutral-400">
      Press Enter to send, Shift+Enter for new line
    </p>
  </div>
</template>

<script setup lang="ts">
import { Send } from 'lucide-vue-next'

interface Props {
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false
})

const emit = defineEmits<{
  send: [message: string]
}>()

const chatStore = useChatStore()
const { namespaceNames } = useNamespaces()

const namespaceOptions = computed(() =>
  namespaceNames.value.map(ns => ({ label: ns, value: ns }))
)

const providerOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Ollama', value: 'ollama' }
]

const canSend = computed(() => {
  return !props.disabled && !chatStore.isLoading && chatStore.inputText.trim().length > 0
})

const handleSend = () => {
  if (canSend.value) {
    emit('send', chatStore.inputText.trim())
  }
}

const handleNewline = (event: KeyboardEvent) => {
  const target = event.target as HTMLTextAreaElement
  const start = target.selectionStart
  const end = target.selectionEnd
  chatStore.inputText = chatStore.inputText.substring(0, start) + '\n' + chatStore.inputText.substring(end)

  // Move cursor after the newline
  nextTick(() => {
    target.selectionStart = target.selectionEnd = start + 1
  })
}
</script>
