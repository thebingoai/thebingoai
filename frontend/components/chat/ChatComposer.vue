<template>
  <div class="home-composer-wrap" ref="composerWrapRef">
    <!-- Floating mention panel anchored to composer -->
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

    <div class="home-composer">
      <!-- File attachment preview strip -->
      <div v-if="attachedFiles.some(f => !f.sent) && !chatStore.isStreaming" class="flex flex-wrap gap-2 mb-2">
        <div v-for="(file, index) in attachedFiles" :key="index" class="group">
          <ChatFilePreview v-if="!file.sent" :file="file" :index="index" @remove="removeFile" />
        </div>
      </div>
      <div v-if="fileErrors.length > 0" class="mb-1">
        <p v-for="(err, i) in fileErrors" :key="i" class="text-[11px] text-[var(--bad)]">
          {{ err.name }}: {{ err.error }}
        </p>
      </div>
      <!-- Contenteditable replaces textarea for inline pill support -->
      <div
        ref="textareaRef"
        role="textbox"
        aria-multiline="true"
        :data-placeholder="placeholder"
        class="home-composer-editor"
        :contenteditable="!chatStore.isStreaming ? 'true' : 'false'"
        :class="{ 'opacity-50 pointer-events-none': chatStore.isStreaming }"
        @input="handleInput"
        @keydown="handleKeydown"
        @paste="handlePaste"
        @mousedown="handleComposerMousedown"
      />
      <div class="home-composer-rail">
        <!-- Mention chip — active state when panel is open -->
        <button
          type="button"
          class="composer-chip"
          :class="{ 'composer-chip--active': isMentionOpen }"
          @click="triggerAt"
          :disabled="chatStore.isStreaming"
        >
          <AtSign class="h-3 w-3" /> Mention
        </button>
        <!-- Attach chip -->
        <button type="button" class="composer-chip" @click="fileInputRef?.click()" :disabled="chatStore.isStreaming">
          <Paperclip class="h-3 w-3" /> Attach
        </button>
        <div style="flex:1" />
        <!-- Ask Bingo button -->
        <button
          type="button"
          class="home-ask-btn"
          :disabled="!chatStore.inputText.trim() || chatStore.isStreaming || (attachedFiles.length > 0 && !allFilesReady)"
          @click="handleSend"
        >
          <Send class="h-3.5 w-3.5" />
          Ask Bingo
        </button>
      </div>
      <!-- hidden file input -->
      <input ref="fileInputRef" type="file" multiple class="sr-only"
        accept="image/png,image/jpeg,image/gif,image/webp,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        @change="handleFileChange"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { AtSign, Paperclip, Send } from 'lucide-vue-next'
import { useChatFileUpload } from '~/composables/useChatFileUpload'
import { useMentions, type MentionItem } from '~/composables/useMentions'
import pillDataset from '~/assets/icons/pill/dataset.svg?raw'
import pillNotion from '~/assets/icons/pill/notion.svg?raw'
import pillDashboard from '~/assets/icons/pill/dashboard.svg?raw'
import pillSkill from '~/assets/icons/pill/skill.svg?raw'

const props = withDefaults(defineProps<{
  placeholder?: string
}>(), {
  placeholder: () => {
    const PLACEHOLDERS = [
      'Which paying customers haven\'t logged in this month?',
      'What\'s driving the spike in support tickets this week?',
      'Compare churn rate across plan tiers for Q3.',
      'Show me top 20 accounts by ARR growth year-over-year.',
    ]
    return PLACEHOLDERS[Math.floor(Math.random() * PLACEHOLDERS.length)]
  },
})

const emit = defineEmits<{
  send: []
}>()

const chatStore = useChatStore()
const { addFiles, attachedFiles, removeFile, allFilesReady } = useChatFileUpload()

const textareaRef = ref<HTMLElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const composerWrapRef = ref<HTMLElement | null>(null)
const fileErrors = ref<{ name: string; error: string }[]>([])

// ── Mention panel ─────────────────────────────────────────
const {
  isMentionOpen,
  mentionLevel,
  filteredGroups,
  activeGroup,
  activeGroupItems,
  openMention,
  closeMention,
  setQuery,
  recordMention,
  clearResolvedMentions,
  restoreSelectionRange,
  isChildMode,
  openMentionForPill,
  getEditingPill,
} = useMentions()

const PILL_ICONS: Record<string, string> = {
  dataset:   pillDataset,
  notion:    pillNotion,
  dashboard: pillDashboard,
  skill:     pillSkill,
}
const MENTION_TYPE_META: Record<string, { typeClass: string }> = {
  connection: { typeClass: 'dataset' }, dashboard: { typeClass: 'dashboard' },
  notion_page: { typeClass: 'notion' }, skill: { typeClass: 'skill' },
}

function extractPlainText(el: HTMLElement): string {
  let text = ''
  for (const node of el.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) text += node.textContent
    else if (node instanceof HTMLElement) {
      if (node.dataset.mention) {
        const child = node.dataset.mentionChild
        text += child ? `@${node.dataset.mention}@${child}` : `@${node.dataset.mention}`
      } else if (node.tagName === 'BR') text += '\n'
      else text += extractPlainText(node)
    }
  }
  return text
}
let isInternalUpdate = false
function syncPlainText() {
  const el = textareaRef.value; if (!el) return
  isInternalUpdate = true; chatStore.inputText = extractPlainText(el); isInternalUpdate = false
}
function getTextBeforeCursor(el: HTMLElement): string {
  const sel = window.getSelection(); if (!sel?.rangeCount) return ''
  const r = sel.getRangeAt(0).cloneRange(); r.selectNodeContents(el)
  const cur = sel.getRangeAt(0); r.setEnd(cur.startContainer, cur.startOffset)
  return r.toString()
}

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
  const el = textareaRef.value; if (!el) return
  const sel = window.getSelection(); if (!sel?.rangeCount) return
  const textBefore = getTextBeforeCursor(el)
  const match = textBefore.match(/(?:^|[\s\n])(@\S*)$/)
  if (!match) { closeMention(); return }
  const atQuery = match[1]
  const cursorRange = sel.getRangeAt(0)
  const container = cursorRange.startContainer
  if (container.nodeType !== Node.TEXT_NODE) { closeMention(); return }
  const textNode = container as Text
  const cursorOffset = cursorRange.startOffset
  const beforeAt = textNode.textContent!.slice(0, cursorOffset - atQuery.length)
  const afterQuery = textNode.textContent!.slice(cursorOffset)
  const meta = MENTION_TYPE_META[item.type] ?? { typeClass: 'default' }
  const pill = document.createElement('span')
  pill.className = `mention-inline-pill mention-inline-pill--${meta.typeClass}`
  pill.contentEditable = 'false'; pill.dataset.mention = item.name; pill.dataset.mentionType = meta.typeClass
  pill.innerHTML = `${PILL_ICONS[meta.typeClass] ?? PILL_ICONS.dataset}<span style="vertical-align:1px">@${item.displayName ?? item.name}</span>`
  const beforeNode = document.createTextNode(beforeAt)
  const afterNode = document.createTextNode(' ' + afterQuery)
  const parent = textNode.parentNode!
  parent.insertBefore(beforeNode, textNode); parent.insertBefore(pill, textNode)
  parent.insertBefore(afterNode, textNode); parent.removeChild(textNode)
  const newRange = document.createRange()
  newRange.setStart(afterNode, 1); newRange.collapse(true)
  sel.removeAllRanges(); sel.addRange(newRange)
  recordMention(item); closeMention(); syncPlainText(); el.focus()
}

// ── Pill interactions (click to re-open panel, click slash to detach) ──
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

const handleComposerMousedown = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  const pill = getPillFromTarget(target)
  if (!pill) return
  e.preventDefault()
  // Detach child on slash click
  if (target.closest('[data-pill-action="detach"]')) {
    detachPillChild(pill)
    return
  }
  // Click on pill body → open mention panel scoped to parent
  openMentionForPill(pill)
}

// Close panel when clicking outside the composer wrap
const handleDocumentMousedown = (e: MouseEvent) => {
  if (!isMentionOpen.value) return
  if (composerWrapRef.value?.contains(e.target as Node)) return
  closeMention()
}
onMounted(() => document.addEventListener('mousedown', handleDocumentMousedown))
onBeforeUnmount(() => document.removeEventListener('mousedown', handleDocumentMousedown))

// ── Composer handlers ────────────────────────────────────
const handleInput = () => {
  syncPlainText()
  const el = textareaRef.value; if (!el) return
  const before = getTextBeforeCursor(el)
  const match = before.match(/(?:^|[\s\n])@(\S*)$/)
  if (match) {
    if (!isMentionOpen.value) openMention(0); else setQuery(match[1])
  } else {
    if (isMentionOpen.value) closeMention()
  }
}

const handlePaste = (e: ClipboardEvent) => {
  e.preventDefault()
  document.execCommand('insertText', false, e.clipboardData?.getData('text/plain') ?? '')
  syncPlainText()
}

const handleKeydown = (e: KeyboardEvent) => {
  if (isMentionOpen.value && e.key === 'Escape') { e.preventDefault(); closeMention(); return }
  if (e.key === 'Backspace') {
    const sel = window.getSelection()
    if (sel?.rangeCount && sel.getRangeAt(0).collapsed) {
      const r = sel.getRangeAt(0)
      let prevNode: Node | null = null
      if (r.startContainer.nodeType === Node.TEXT_NODE && r.startOffset === 0)
        prevNode = r.startContainer.previousSibling
      if (prevNode instanceof HTMLElement && prevNode.dataset.mention) {
        prevNode.remove(); syncPlainText(); e.preventDefault(); return
      }
    }
  }
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

const handleSend = () => {
  if (!chatStore.inputText.trim() || chatStore.isStreaming) return
  clearResolvedMentions()
  emit('send')
  nextTick(() => {
    const el = textareaRef.value; if (el) el.innerHTML = ''
    isInternalUpdate = true; chatStore.inputText = ''; isInternalUpdate = false
  })
}

const triggerAt = () => {
  const el = textareaRef.value; if (!el) return
  el.focus()
  document.execCommand('insertText', false, '@')
  handleInput()
}

const handleFileChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  if (input.files) {
    const rejections = await addFiles(Array.from(input.files))
    fileErrors.value = rejections
  }
  input.value = ''
}
</script>

<style scoped>
/* ── Composer wrapper (anchors floating mention panel) ── */
.home-composer-wrap {
  position: relative;
  margin-top: 36px;
}

/* ── Composer ───────────────────────────────────────── */
.home-composer {
  border: 1px solid var(--line-2);
  border-radius: 20px;
  background: var(--paper-0);
  padding: 18px 20px 12px;
}

.home-composer-editor {
  width: 100%;
  min-height: 60px;
  max-height: 200px;
  overflow-y: auto;
  font-family: var(--font-sans);
  font-size: 17px;
  color: var(--ink-0);
  line-height: 1.5;
  outline: none;
  word-break: break-word;
  white-space: pre-wrap;
  position: relative;
}
.home-composer-editor:empty::before {
  content: attr(data-placeholder);
  color: var(--ink-3);
  pointer-events: none;
}

.home-composer-rail {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

/* Active state for Mention chip when panel is open */
.composer-chip--active {
  border-color: var(--ember) !important;
  background: var(--ember-wash) !important;
  color: var(--ember) !important;
}

.home-ask-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  background: var(--ink-0);
  color: var(--paper-0);
  border: 1px solid var(--ink-0);
  font-size: 13px;
  font-weight: 500;
  font-family: var(--font-sans);
  cursor: pointer;
  letter-spacing: -0.005em;
  transition: opacity 0.15s;
}
.home-ask-btn:hover:not(:disabled) {
  opacity: 0.82;
}
.home-ask-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
</style>
