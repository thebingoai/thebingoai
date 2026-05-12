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
        <!-- Skills chip — opens skill picker via ⌘K equivalent -->
        <button
          type="button"
          class="composer-chip"
          :disabled="chatStore.isStreaming"
          @click="openSkillPicker"
        >
          <Sparkles class="h-3 w-3" /> Skills
          <span style="font-family:var(--font-mono);font-size:9.5px;color:var(--ink-3);margin-left:2px;">⌘K</span>
        </button>
        <div style="flex:1" />
        <!-- Ask Bingo button -->
        <button
          type="button"
          class="home-ask-btn"
          :disabled="!chatStore.inputText.trim() || chatStore.isStreaming"
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
import { AtSign, Paperclip, Sparkles, Send } from 'lucide-vue-next'
import { useChatFileUpload } from '~/composables/useChatFileUpload'
import { useMentions, type MentionItem } from '~/composables/useMentions'

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
const { addFiles } = useChatFileUpload()

const textareaRef = ref<HTMLElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
const composerWrapRef = ref<HTMLElement | null>(null)

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
  dataset:   `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`,
  notion:    `<svg width="11" height="11" viewBox="0 0 59.9 62.6" style="flex-shrink:0"><path fill="#FFFFFF" d="M3.8 2.7l34.6-2.6c4.2-.4 5.3-.1 8 1.8l11.1 7.8c1.8 1.3 2.4 1.7 2.4 3.2v42.7c0 2.7-1 4.3-4.4 4.5l-40.2 2.4c-2.6.1-3.8-.2-5.1-1.9L2.1 50.1c-1.5-2-2.1-3.4-2.1-5.1V7C0 4.8 1 2.9 3.8 2.7z"/><path fill-rule="evenodd" clip-rule="evenodd" d="M38.4.1L3.8 2.7C1 2.9 0 4.8 0 7v38c0 1.7.6 3.2 2.1 5.1l8.1 10.6c1.3 1.7 2.6 2.1 5.1 1.9l40.2-2.4c3.4-.2 4.4-1.8 4.4-4.5V12.9c0-1.4-.5-1.8-2.2-3l-.3-.2L46.4 2C43.8 0 42.7-.2 38.4.1zM16.2 12.2c-3.3.2-4 .3-5.9-1.3L5.6 7.2c-.5-.5-.3-1.1 1-1.2l33.3-2.4c2.8-.2 4.2.7 5.3 1.6l5.7 4.1c.3.1.9.8.1.8l-34.4 2.1-.4.1zM12.4 55.3V19c0-1.6.5-2.3 1.9-2.4l39.5-2.3c1.3-.1 1.9.7 1.9 2.3v36c0 1.6-.3 2.9-2.4 3l-37.8 2.2c-1.8.1-2.8-.7-2.8-2.6zm37.3-34.3c.2 1.1 0 2.2-1.1 2.3l-1.8.4v26.8c-1.6.9-3 1.3-4.2 1.3-1.9 0-2.4-.6-3.9-2.4L26.7 30.6v18.1l3.8.9s0 2.2-3 2.2l-8.4.5c-.2-.5 0-1.7.8-1.9l2.2-.6v-24l-3-.3c-.2-1.1.4-2.7 2.1-2.8l9-.6 12.4 19V24.3l-3.2-.4c-.2-1.3.7-2.3 1.9-2.4l5.7-.8z"/></svg>`,
  dashboard: `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>`,
  skill:     `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
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

const openSkillPicker = () => {
  const el = textareaRef.value; if (!el) return
  el.focus()
  document.execCommand('insertText', false, '@')
  nextTick(() => handleInput())
}

const handleFileChange = async (e: Event) => {
  const input = e.target as HTMLInputElement
  if (input.files) await addFiles(Array.from(input.files))
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
  box-shadow: var(--shadow-3);
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
