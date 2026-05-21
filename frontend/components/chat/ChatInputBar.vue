<template>
  <!-- Outer wrapper -->
  <div ref="containerRef" class="relative">
    <div class="px-14 pb-6">
      <!-- Out-of-credits banner -->
      <div
        v-if="isExhausted && featureConfig?.credits_enabled !== false"
        class="mb-3 rounded-xl border border-[var(--warn)] bg-[color-mix(in_oklch,var(--warn)_8%,var(--paper-0))] px-4 py-3 text-[13px] text-[var(--ink-0)] flex items-center justify-between gap-3"
      >
        <span>Daily credits used up. Resets at midnight.</span>
        <NuxtLink to="/settings?tab=credits" class="font-medium underline hover:opacity-80 whitespace-nowrap">
          Add your own API key →
        </NuxtLink>
      </div>

      <div class="max-w-[760px] mx-auto relative">
        <!-- Floating mention panel -->
        <Transition
          enter-active-class="transition-all duration-100 ease-out"
          enter-from-class="opacity-0 translate-y-1"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-75 ease-in"
          leave-from-class="opacity-100 translate-y-0"
          leave-to-class="opacity-0 translate-y-1"
        >
          <ChatMentionPanel
            v-if="isMentionOpen"
            class="absolute bottom-full left-0 mb-2 z-50"
            :filtered-groups="filteredGroups"
            :active-group="activeGroup"
            :active-group-items="activeGroupItems"
            :mention-level="mentionLevel"
            @select="handleMentionSelect"
            @close="closeMention()"
            @back="() => {}"
          />
        </Transition>

        <form
          @submit.prevent="handleSubmit"
          @dragover.prevent
          @drop.prevent="handleDrop"
          class="rounded-2xl border border-[var(--line-2)] bg-[var(--paper-0)] shadow-[var(--shadow-2)] flex flex-col focus-within:border-[var(--ink-3)] transition-colors px-4 pt-3.5 pb-2.5"
        >
          <!-- Attachment preview strip (hidden during streaming so retained processing files don't reappear) -->
          <div v-if="attachedFiles.some(f => !f.sent) && !chatStore.isStreaming" class="flex flex-wrap gap-2 mb-2">
            <div v-for="(file, index) in attachedFiles" :key="index" class="group">
              <ChatFilePreview v-if="!file.sent" :file="file" :index="index" @remove="removeFile" />
            </div>
          </div>

          <!-- Inline error messages -->
          <div v-if="fileErrors.length > 0" class="mb-1">
            <p v-for="(err, i) in fileErrors" :key="i" class="text-[11px] text-[var(--bad)]">
              {{ err.name }}: {{ err.error }}
            </p>
          </div>

          <!-- ── Contenteditable composer (replaces textarea) ── -->
          <div
            ref="editorRef"
            role="textbox"
            aria-multiline="true"
            data-placeholder="Ask a question about your data…"
            class="composer-editor pb-2"
            :contenteditable="!chatStore.isStreaming ? 'true' : 'false'"
            :class="{ 'opacity-50 pointer-events-none': chatStore.isStreaming }"
            @input="handleInput"
            @keydown="handleKeydown"
            @paste="handlePaste"
            @mousedown="handleEditorMousedown"
          />

          <!-- Bottom action rail: Mention · Attach · Skill · New topic -->
          <div class="flex items-center gap-1.5 pt-2.5 mt-0.5 border-t border-dashed border-[var(--line)]">
            <button
              type="button"
              :disabled="chatStore.isStreaming"
              @click="triggerMention"
              title="Mention a dataset, dashboard or skill"
              class="composer-chip disabled:opacity-40"
            >
              <AtSign class="h-3 w-3" /> Mention
            </button>

            <button
              type="button"
              :disabled="chatStore.isStreaming"
              @click="fileInputRef?.click()"
              title="Attach files (max 50 MB)"
              class="composer-chip disabled:opacity-40"
            >
              <Paperclip class="h-3 w-3" /> Attach
            </button>

            <button
              v-if="isPermanentThread"
              type="button"
              :disabled="chatStore.isStreaming || isFreshTopic"
              @click="onClickNewTopic"
              title="New Topic"
              class="composer-chip disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Scissors class="h-3 w-3" /> New topic
            </button>

            <div class="flex-1" />
            <span class="font-mono text-[10.5px] text-[var(--ink-3)] mr-1 hidden md:inline">
              ⏎ send · ⇧⏎ new line
            </span>

            <button
              type="submit"
              :disabled="!chatStore.inputText.trim() || chatStore.isStreaming || (attachedFiles.length > 0 && !allFilesReady)"
              class="flex h-8 w-8 items-center justify-center rounded-[10px] bg-[var(--ink-0)] text-[var(--paper-0)] disabled:opacity-40 hover:opacity-80 transition-opacity"
            >
              <ArrowUp class="h-4 w-4" />
            </button>
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

        <!-- Meta strip below composer -->
        <div class="flex items-center gap-2 mt-2 px-0.5 text-[11px] text-[var(--ink-2)]">
          <span class="text-[var(--ok)]">●</span>
          <span v-if="datasetsInContext > 0">{{ datasetsInContext }} dataset{{ datasetsInContext !== 1 ? 's' : '' }} in context</span>
          <span v-else>no datasets attached</span>
          <template v-if="datasetsInContext > 0">
            <span class="text-[var(--line-2)]">·</span>
            <span>context: <b class="text-[var(--ink-0)]">—</b></span>
          </template>
          <div class="flex-1" />
          <span v-if="featureConfig?.credits_enabled !== false">{{ Math.round(remaining) }} credits left today</span>
        </div>
      </div>
    </div>
    <UiDialog v-model:open="showResetConfirm" title="Start a new topic?" size="sm">
      <p class="text-[13px] text-[var(--ink-2)] leading-relaxed">
        Bingo will clear the current context. Past messages stay visible but won't influence the next reply.
      </p>
      <template #footer>
        <div class="flex items-center justify-end gap-2">
          <button
            type="button"
            class="px-3 py-1.5 rounded-md text-[12px] text-[var(--ink-1)] hover:bg-[var(--paper-2)] transition-colors"
            @click="showResetConfirm = false"
          >
            Cancel
          </button>
          <button
            type="button"
            class="px-3 py-1.5 rounded-md text-[12px] font-medium bg-[var(--ember)] text-white hover:opacity-90 transition-opacity"
            @click="confirmReset"
          >
            Confirm
          </button>
        </div>
      </template>
    </UiDialog>
  </div>
</template>

<script setup lang="ts">
import { Scissors, ArrowUp, Paperclip, AtSign } from 'lucide-vue-next'
import UiDialog from '~/components/ui/UiDialog.vue'
import { useMentions, type MentionItem } from '~/composables/useMentions'
import pillDataset from '~/assets/icons/pill/dataset.svg?raw'
import pillNotion from '~/assets/icons/pill/notion.svg?raw'
import pillDashboard from '~/assets/icons/pill/dashboard.svg?raw'
import pillSkill from '~/assets/icons/pill/skill.svg?raw'
import pillPerson from '~/assets/icons/pill/person.svg?raw'

const chatStore = useChatStore()
const emit = defineEmits<{ send: []; reset: [] }>()

const { isExhausted, remaining } = useCreditBalance()
const { config: featureConfig } = useFeatureConfig()

const isPermanentThread = computed(() =>
  chatStore.currentConversation?.type === 'permanent'
)

const isFreshTopic = computed(() => {
  const lastMsg = chatStore.messages[chatStore.messages.length - 1]
  const noPriorContent =
    chatStore.messages.length === 0 || lastMsg?.source === 'context_reset'
  return noPriorContent && !chatStore.inputText.trim()
})

const showResetConfirm = ref(false)

const onClickNewTopic = () => {
  if (isFreshTopic.value) return
  showResetConfirm.value = true
}

const confirmReset = () => {
  showResetConfirm.value = false
  emit('reset')
}

const editorRef  = ref<HTMLElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const containerRef = ref<HTMLElement | null>(null)

const { attachedFiles, addFiles, removeFile, allFilesReady } = useChatFileUpload()
const fileErrors = ref<Array<{ name: string; error: string }>>([])

const datasetsInContext = computed(() => chatStore.conversationDatasets?.length ?? 0)

// ── Mention panel ─────────────────────────────────────────
const {
  isMentionOpen, mentionLevel,
  filteredGroups, activeGroup, activeGroupItems,
  openMention, closeMention, goBackToRoot, setQuery,
  recordMention, clearResolvedMentions, restoreSelectionRange,
  isChildMode, openMentionForPill, getEditingPill,
} = useMentions()

// ── Pill icon SVGs (inline HTML — Vue components can't go in innerHTML) ──
const PILL_ICONS: Record<string, string> = {
  dataset:   pillDataset,
  notion:    pillNotion,
  dashboard: pillDashboard,
  skill:     pillSkill,
  person:    pillPerson,
}
const MENTION_TYPE_META: Record<string, { typeClass: string }> = {
  connection:  { typeClass: 'dataset' },
  dashboard:   { typeClass: 'dashboard' },
  notion_page: { typeClass: 'notion' },
  skill:       { typeClass: 'skill' },
  person:      { typeClass: 'person' },
}

// ── Plain-text extraction ─────────────────────────────────
function extractPlainText(el: HTMLElement): string {
  let text = ''
  for (const node of el.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      text += node.textContent
    } else if (node instanceof HTMLElement) {
      if (node.dataset.mention) {
        const child = node.dataset.mentionChild
        text += child ? `@${node.dataset.mention}@${child}` : `@${node.dataset.mention}`
      } else if (node.tagName === 'BR') {
        text += '\n'
      } else if (node.tagName === 'DIV' || node.tagName === 'P') {
        // Browser wraps new lines in divs/p in contenteditable
        text += '\n' + extractPlainText(node)
      } else {
        text += extractPlainText(node)
      }
    }
  }
  return text
}

let isInternalUpdate = false

function syncPlainText() {
  const el = editorRef.value
  if (!el) return
  isInternalUpdate = true
  chatStore.inputText = extractPlainText(el)
  isInternalUpdate = false
}

// ── Text before cursor (for @ detection) ─────────────────
function getTextBeforeCursor(el: HTMLElement): string {
  const sel = window.getSelection()
  if (!sel?.rangeCount) return ''
  const r = sel.getRangeAt(0).cloneRange()
  r.selectNodeContents(el)
  const cur = sel.getRangeAt(0)
  r.setEnd(cur.startContainer, cur.startOffset)
  return r.toString()
}

// ── Input handler ─────────────────────────────────────────
const handleInput = () => {
  syncPlainText()
  const el = editorRef.value
  if (!el) return
  const before = getTextBeforeCursor(el)
  const match = before.match(/(?:^|[\s\n])@(\S*)$/)
  if (match) {
    const query = match[1]
    if (!isMentionOpen.value) {
      openMention(0)
    } else {
      setQuery(query)
    }
  } else {
    if (isMentionOpen.value) closeMention()
  }
}

// ── Pill interaction helpers ────────────────────────────
function getPillFromTarget(target: HTMLElement): HTMLElement | null {
  return target.closest('[data-mention]') as HTMLElement | null
}
function detachPillChild(pill: HTMLElement) {
  const typeClass = pill.dataset.mentionType ?? 'dataset'
  const icon = PILL_ICONS[typeClass] ?? PILL_ICONS.dataset
  const parentName = pill.dataset.mention!
  delete pill.dataset.mentionChild
  delete pill.dataset.mentionChildDisplay
  pill.className = `mention-inline-pill mention-inline-pill--${typeClass}`
  pill.innerHTML = `${icon}<span style="vertical-align:1px">@${parentName}</span>`
  syncPlainText()
}
const handleEditorMousedown = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  const pill = getPillFromTarget(target)
  if (!pill) return
  e.preventDefault()
  if (target.closest('[data-pill-action="detach"]')) { detachPillChild(pill); return }
  openMentionForPill(pill)
}

// ── Mention pill insertion ────────────────────────────────
const handleMentionSelect = (item: MentionItem) => {
  // Child mode: update existing pill with child
  if (isChildMode.value) {
    const pill = getEditingPill()
    if (!pill) { closeMention(); return }
    const typeClass = pill.dataset.mentionType ?? 'dataset'
    const icon = PILL_ICONS[typeClass] ?? PILL_ICONS.dataset
    const parentName = pill.dataset.mention!
    const childName = item.displayName ?? item.name
    pill.dataset.mentionChild = item.name
    pill.dataset.mentionChildDisplay = childName
    pill.className = `mention-pc mention-pc--${typeClass}`
    pill.innerHTML = [
      `<span class="mention-pc__parent">${icon}<span style="vertical-align:1px">@${parentName}</span></span>`,
      `<span class="mention-pc__sep" data-pill-action="detach">/</span>`,
      `<span class="mention-pc__child">${childName}</span>`,
    ].join('')
    recordMention(item)
    closeMention()
    syncPlainText()
    return
  }

  // Restore cursor to where @ was typed (clicking the panel loses it)
  if (!restoreSelectionRange()) { closeMention(); return }
  const el = editorRef.value
  if (!el) return
  const sel = window.getSelection()
  if (!sel?.rangeCount) return

  const textBefore = getTextBeforeCursor(el)
  const match = textBefore.match(/(?:^|[\s\n])(@\S*)$/)
  if (!match) { closeMention(); return }

  const atQuery = match[1]   // "@query" including @
  const cursorRange = sel.getRangeAt(0)
  const container = cursorRange.startContainer
  const cursorOffset = cursorRange.startOffset

  // Only proceed if cursor is in a text node (normal typing position)
  if (container.nodeType !== Node.TEXT_NODE) { closeMention(); return }

  const textNode = container as Text
  const beforeAt = textNode.textContent!.slice(0, cursorOffset - atQuery.length)
  const afterQuery = textNode.textContent!.slice(cursorOffset)

  // Build pill element
  const meta = MENTION_TYPE_META[item.type] ?? { typeClass: 'default' }
  const icon = PILL_ICONS[meta.typeClass] ?? PILL_ICONS.dataset
  const pill = document.createElement('span')
  pill.className = `mention-inline-pill mention-inline-pill--${meta.typeClass}`
  pill.contentEditable = 'false'
  pill.dataset.mention = item.name
  pill.dataset.mentionType = meta.typeClass
  pill.innerHTML = `${icon}<span style="vertical-align:1px">@${item.displayName ?? item.name}</span>`

  // Split text node: [before@][pill][space+after]
  const beforeNode = document.createTextNode(beforeAt)
  const afterNode  = document.createTextNode(' ' + afterQuery)
  const parent = textNode.parentNode!
  parent.insertBefore(beforeNode, textNode)
  parent.insertBefore(pill, textNode)
  parent.insertBefore(afterNode, textNode)
  parent.removeChild(textNode)

  // Move cursor to after the trailing space
  const newRange = document.createRange()
  newRange.setStart(afterNode, 1)
  newRange.collapse(true)
  sel.removeAllRanges()
  sel.addRange(newRange)

  recordMention(item)
  closeMention()
  syncPlainText()
  el.focus()
}

// ── Trigger @ mention via chip button ─────────────────────
const triggerMention = () => {
  const el = editorRef.value
  if (!el) return
  el.focus()
  document.execCommand('insertText', false, '@')
  handleInput()
}

// ── Keyboard handler ──────────────────────────────────────
const handleKeydown = (event: KeyboardEvent) => {
  // Escape: close or go back in mention panel
  if (isMentionOpen.value && event.key === 'Escape') {
    event.preventDefault()
    mentionLevel.value === 'items' ? goBackToRoot() : closeMention()
    return
  }

  // Backspace: delete an entire pill if cursor is right after one
  if (event.key === 'Backspace') {
    const sel = window.getSelection()
    if (sel?.rangeCount && sel.getRangeAt(0).collapsed) {
      const r = sel.getRangeAt(0)
      // Check sibling just before cursor
      let prevNode: Node | null = null
      if (r.startContainer.nodeType === Node.TEXT_NODE && r.startOffset === 0) {
        prevNode = r.startContainer.previousSibling
      } else if (r.startContainer.nodeType === Node.ELEMENT_NODE) {
        const el2 = r.startContainer as Element
        prevNode = el2.childNodes[r.startOffset - 1] ?? null
      }
      if (prevNode instanceof HTMLElement && prevNode.dataset.mention) {
        prevNode.remove()
        syncPlainText()
        event.preventDefault()
        return
      }
    }
  }

  // Enter: submit (or Shift+Enter for newline)
  if (event.key === 'Enter') {
    if (event.shiftKey) {
      // Allow default browser newline behavior in contenteditable
      return
    }
    event.preventDefault()
    handleSubmit()
  }
}

// ── Paste: strip HTML, only plain text ────────────────────
const handlePaste = (event: ClipboardEvent) => {
  event.preventDefault()
  const text = event.clipboardData?.getData('text/plain') ?? ''
  document.execCommand('insertText', false, text)
  syncPlainText()
}

// ── Submit ────────────────────────────────────────────────
const handleSubmit = () => {
  if (!chatStore.inputText.trim() || chatStore.isStreaming) return
  emit('send')
  clearResolvedMentions()
  nextTick(() => {
    const el = editorRef.value
    if (el) el.innerHTML = ''
    isInternalUpdate = true
    chatStore.inputText = ''
    isInternalUpdate = false
  })
}

// ── Watch for external inputText changes (e.g. skill card click) ─
watch(() => chatStore.inputText, (val) => {
  if (isInternalUpdate) return
  const el = editorRef.value
  if (!el) return
  if (extractPlainText(el) !== val) {
    // Set as plain text (no pills for programmatically-set content)
    el.textContent = val
    // Move cursor to end
    const sel = window.getSelection()
    const r = document.createRange()
    r.selectNodeContents(el)
    r.collapse(false)
    sel?.removeAllRanges()
    sel?.addRange(r)
  }
})

// ── Click outside → close panel ───────────────────────────
const handleDocumentMousedown = (e: MouseEvent) => {
  if (!isMentionOpen.value) return
  if (containerRef.value?.contains(e.target as Node)) return
  closeMention()
}
onMounted(() => document.addEventListener('mousedown', handleDocumentMousedown))
onBeforeUnmount(() => document.removeEventListener('mousedown', handleDocumentMousedown))

// ── File handling ─────────────────────────────────────────
const handleFileChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  if (!input.files) return
  const rejections = await addFiles(Array.from(input.files))
  fileErrors.value = rejections
  input.value = ''
  if (rejections.length > 0) setTimeout(() => { fileErrors.value = [] }, 4000)
}

const handleDrop = async (e: DragEvent) => {
  if (!e.dataTransfer?.files) return
  const rejections = await addFiles(Array.from(e.dataTransfer.files))
  fileErrors.value = rejections
  if (rejections.length > 0) setTimeout(() => { fileErrors.value = [] }, 4000)
}
</script>
