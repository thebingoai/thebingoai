<template>
  <div class="flex flex-1 overflow-hidden">

    <!-- ── New Task / Home screen (no active thread) ───────── -->
    <template v-if="!chatStore.currentThreadId">
      <div class="flex flex-1 flex-col min-w-0 min-h-0">
        <HomeNewTaskScreen @send="handleSend" />
      </div>

      <!-- Desktop right pane (Datasets) — always visible -->
      <template v-if="!isMobile">
        <div class="right-pane-handle" @mousedown="startRightResize" />
        <div
          class="shrink-0 border-l border-[var(--line)] overflow-hidden flex flex-col"
          :style="{ width: `${rightPaneWidth}px` }"
        >
          <ConversationInfoPanel />
        </div>
      </template>
    </template>

    <!-- ── Active thread (conversation in progress) ────────── -->
    <template v-else>
      <div class="flex flex-1 flex-col min-w-0 min-h-0">
        <ChatThread @send-action="handleAction" />
        <ChatInputBar @send="handleSend" @reset="handleReset" />
      </div>

      <!-- Desktop right pane -->
      <template v-if="!isMobile">
        <div class="right-pane-handle" @mousedown="startRightResize" />
        <div
          class="shrink-0 border-l border-[var(--line)] overflow-hidden flex flex-col"
          :style="{ width: `${rightPaneWidth}px` }"
        >
          <ConversationInfoPanel />
        </div>
      </template>
    </template>

    <!-- Mobile: full-screen overlay panel -->
    <Transition name="slide-up">
      <div
        v-if="isMobile && chatStore.infoPanelOpen"
        class="fixed inset-0 z-50 bg-[var(--paper-0)] flex flex-col"
      >
        <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--line)]">
          <span class="text-[13px] font-medium text-[var(--ink-0)]">Datasets</span>
          <button @click="chatStore.toggleInfoPanel()" class="p-1 rounded hover:bg-[var(--paper-2)]">
            <X class="h-5 w-5 text-[var(--ink-2)]" />
          </button>
        </div>
        <div class="flex-1 overflow-y-auto">
          <ConversationInfoPanel />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { useChatFileUpload } from '~/composables/useChatFileUpload'

const chatStore = useChatStore()
const chat = useChat()
const { getFileIds, clearFiles } = useChatFileUpload()
const { isMobile } = useIsMobile()

// ── Right pane resize ─────────────────────────────────────
const RIGHT_MIN = 280
const RIGHT_MAX = 600
const MIDDLE_MIN = 400
const rightPaneWidth = ref(440)
let resizeStartX = 0
let resizeStartW = 0

const startRightResize = (e: MouseEvent) => {
  resizeStartX = e.clientX
  resizeStartW = rightPaneWidth.value
  document.addEventListener('mousemove', onRightResize)
  document.addEventListener('mouseup', stopRightResize)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

const onRightResize = (e: MouseEvent) => {
  const delta = resizeStartX - e.clientX
  const desired = resizeStartW + delta
  const clamped = Math.min(Math.max(desired, RIGHT_MIN), RIGHT_MAX)
  rightPaneWidth.value = clamped
}

const stopRightResize = () => {
  document.removeEventListener('mousemove', onRightResize)
  document.removeEventListener('mouseup', stopRightResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

// ── Lifecycle ─────────────────────────────────────────────
onMounted(() => {
  if (isMobile.value) {
    chatStore.infoPanelOpen = false
  } else {
    chatStore.infoPanelOpen = true
  }
})

// ── Message handlers ──────────────────────────────────────
const handleSend = () => {
  if (chatStore.inputText.trim()) {
    const fileIds = getFileIds()
    chat.sendMessage(chatStore.inputText, fileIds)
    clearFiles()
  }
}

const handleAction = (text: string, source?: string) => {
  if (!chatStore.isStreaming) {
    chat.sendMessage(text, [], source ? { source: source as any } : undefined)
  }
}

const handleReset = () => {
  chat.resetContext()
}

definePageMeta({
  middleware: 'auth'
})
</script>

<style scoped>
.right-pane-handle {
  width: 4px;
  flex-shrink: 0;
  cursor: col-resize;
  background: transparent;
  transition: background 0.15s;
  position: relative;
}
.right-pane-handle::after {
  content: '';
  position: absolute;
  inset-y: 0;
  left: -3px;
  right: -3px;
}
.right-pane-handle:hover {
  background: var(--ember);
}
</style>
