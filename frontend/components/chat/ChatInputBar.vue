<template>
  <!-- Outer relative wrapper anchors the mention panel -->
  <div ref="containerRef" class="relative">
    <!-- Slide-up mention panel -->
    <Transition
      enter-active-class="transition-all duration-100 ease-out"
      enter-from-class="opacity-0 translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-75 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-2"
    >
      <ChatMentionPanel
        v-if="isMentionOpen"
        class="absolute bottom-full left-4 right-4 md:left-16 md:right-16 mb-2 z-50"
        :filtered-groups="filteredGroups"
        :active-group="activeGroup"
        :active-group-items="activeGroupItems"
        :mention-level="mentionLevel"
        @select="handleMentionSelect"
        @close="closeMention()"
        @back="() => {}"
      />
    </Transition>

    <div class="px-4 pb-4 md:px-16">
      <!-- Out-of-credits banner -->
      <div
        v-if="isExhausted"
        class="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 flex items-center justify-between gap-3"
      >
        <span>Daily credits used up. Resets at midnight.</span>
        <NuxtLink to="/settings?tab=credits" class="font-medium underline hover:text-amber-900 whitespace-nowrap">
          Add your own API key →
        </NuxtLink>
      </div>

      <form
        @submit.prevent="handleSubmit"
        @dragover.prevent
        @drop.prevent="handleDrop"
        class="shadow-lg rounded-xl border border-gray-300 dark:border-neutral-600 flex flex-col focus-within:border-gray-400 dark:focus-within:border-neutral-500 transition-colors dark:bg-neutral-800"
      >
        <!-- Attachment preview strip -->
        <div
          v-if="attachedFiles.length > 0"
          class="flex flex-wrap gap-2 px-4 pt-3"
        >
          <div
            v-for="(file, index) in attachedFiles"
            :key="index"
            class="group"
          >
            <ChatFilePreview
              :file="file"
              :index="index"
              @remove="removeFile"
            />
          </div>
        </div>

        <!-- Inline error messages from file rejections -->
        <div v-if="fileErrors.length > 0" class="px-4 pt-2">
          <p
            v-for="(err, i) in fileErrors"
            :key="i"
            class="text-xs text-red-500"
          >
            {{ err.name }}: {{ err.error }}
          </p>
        </div>

        <textarea
          ref="textareaRef"
          v-model="chatStore.inputText"
          placeholder="Ask a question about your data…"
          rows="1"
          class="w-full resize-none px-4 pt-3 pb-2 max-h-48 overflow-y-auto bg-transparent outline-none rounded-t-xl text-gray-900 dark:text-neutral-100 placeholder-gray-400 dark:placeholder-neutral-500"
          :disabled="chatStore.isStreaming"
          @input="handleInput"
          @keydown="handleKeydown"
        />
        <div class="flex items-center justify-between gap-1.5 px-3 pb-3">
          <span class="flex-1" />

          <div class="flex gap-1.5">
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
          <!-- Paperclip button -->
          <button
            type="button"
            :disabled="chatStore.isStreaming"
            @click="fileInputRef?.click()"
            :class="[
              'flex h-8 w-8 items-center justify-center rounded-full transition-colors cursor-pointer',
              chatStore.isStreaming
                ? 'text-gray-300 opacity-40'
                : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
            ]"
            title="Attach files (max 50 MB)"
          >
            <Paperclip class="h-4 w-4" />
          </button>
          <!-- Send button -->
          <button
            type="submit"
            :disabled="!chatStore.inputText.trim() || chatStore.isStreaming || (attachedFiles.length > 0 && !allFilesReady)"
            class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-900 text-white disabled:opacity-40 hover:bg-gray-700 dark:bg-neutral-200 dark:text-neutral-900 dark:hover:bg-white transition-colors"
          >
            <ArrowUp class="h-4 w-4" />
          </button>
          </div>
        </div>

        <!-- Hidden file input -->
        <input
          type="file"
          multiple
          accept="image/png,image/jpeg,image/gif,image/webp,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ref="fileInputRef"
          @change="handleFileChange"
          class="sr-only"
        />
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Scissors, ArrowUp, Paperclip } from 'lucide-vue-next'
import { useMentions, type MentionItem } from '~/composables/useMentions'

const chatStore = useChatStore()
const emit = defineEmits<{
  send: []
  reset: []
}>()

const { isExhausted } = useCreditBalance()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)

const { attachedFiles, addFiles, removeFile, allFilesReady } = useChatFileUpload()

interface FileRejection {
  name: string
  error: string
}
const fileErrors = ref<FileRejection[]>([])

const isPermanentConversation = computed(() => chatStore.currentConversation?.type === 'permanent')

// --- Mention panel ---

const {
  isMentionOpen,
  mentionLevel,
  filteredGroups,
  activeGroup,
  activeGroupItems,
  mentionAnchor,
  openMention,
  closeMention,
  goBackToRoot,
  setQuery,
  recordMention,
  clearResolvedMentions,
} = useMentions()

const handleMentionSelect = (item: MentionItem) => {
  const el = textareaRef.value
  if (!el) return
  const token = `@${item.name} `
  const anchor = mentionAnchor.value ?? -1
  if (anchor < 0) return
  // Replace from the '@' position up to the current cursor
  const before = el.value.slice(0, anchor)
  const after = el.value.slice(el.selectionStart)
  chatStore.inputText = before + token + after
  recordMention(item)
  closeMention()
  nextTick(() => {
    el.selectionStart = el.selectionEnd = anchor + token.length
    autoResize()
    el.focus()
  })
}

// Close mention panel on click outside the container
const handleDocumentMousedown = (event: MouseEvent) => {
  if (!isMentionOpen.value) return
  if (containerRef.value?.contains(event.target as Node)) return
  closeMention()
}

onMounted(() => document.addEventListener('mousedown', handleDocumentMousedown))
onBeforeUnmount(() => document.removeEventListener('mousedown', handleDocumentMousedown))

// --- Textarea helpers ---

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

// Detect whether the cursor is directly after an @-token and open/update the panel
const handleInput = () => {
  autoResize()
  const el = textareaRef.value
  if (!el) return
  const before = el.value.slice(0, el.selectionStart)
  // Match @ preceded by start-of-string, space, or newline
  const match = before.match(/(?:^|[\s\n])@(\S*)$/)
  if (match) {
    const query = match[1]
    const anchorPos = el.selectionStart - query.length - 1
    if (!isMentionOpen.value) {
      // First time seeing @: open panel (resets to root level)
      openMention(anchorPos)
    } else {
      // Panel already open: just update the search query for the current level
      setQuery(query)
    }
  } else {
    if (isMentionOpen.value) closeMention()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  const el = textareaRef.value

  // Escape: go back to root if in items level, otherwise close
  if (isMentionOpen.value && event.key === 'Escape') {
    event.preventDefault()
    if (mentionLevel.value === 'items') {
      goBackToRoot()
    } else {
      closeMention()
    }
    return
  }

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
    clearResolvedMentions()
  }
}

// --- File handling ---

const handleFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (!input.files) return
  const rejections = await addFiles(Array.from(input.files))
  fileErrors.value = rejections
  input.value = ''
  if (rejections.length > 0) {
    setTimeout(() => { fileErrors.value = [] }, 4000)
  }
}

const handleDrop = async (event: DragEvent) => {
  if (!event.dataTransfer?.files) return
  const rejections = await addFiles(Array.from(event.dataTransfer.files))
  fileErrors.value = rejections
  if (rejections.length > 0) {
    setTimeout(() => { fileErrors.value = [] }, 4000)
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
