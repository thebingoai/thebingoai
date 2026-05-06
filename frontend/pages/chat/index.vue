<template>
  <div class="flex flex-1 overflow-hidden relative" :class="{ 'enter-from-send': enterFromSend }">

    <!-- ── Main content area with view transition ─────────── -->
    <!-- mode="out-in" matches Nuxt's page-fade-slide (Bingo↔Dashboard) feel:
         old view fully leaves, then new view enters. -->
    <Transition name="view-switch" mode="out-in">
      <!-- New Task / Home screen (no active thread) -->
      <div v-if="showNewTaskScreen" key="new-task" class="flex flex-1 flex-col min-w-0 min-h-0" :class="{ 'new-task-sending': sendingFromNewTask }">
        <HomeNewTaskScreen :is-sending="sendingFromNewTask" @send="handleSend" />
      </div>

      <!-- Active thread (conversation in progress) -->
      <div v-else-if="chatStore.currentThreadId || isTransitioning" key="chat" class="flex flex-1 flex-col min-w-0 min-h-0">
        <!-- Inner page-fade-slide handles task A → task B (mirrors Bingo↔Dashboard).
             :name="''" when currentThreadId is null suppresses CSS during outer transitions
             (going to/from New Task), preventing the previous double-animation. -->
        <div class="flex-1 min-h-0 flex flex-col overflow-hidden">
          <Transition :name="chatStore.currentThreadId ? 'page-fade-slide' : ''" mode="out-in">
            <ChatThread v-if="chatStore.currentThreadId" :key="chatStore.currentThreadId" @send-action="handleAction" />
          </Transition>
        </div>
        <ChatInputBar @send="handleSend" @reset="handleReset" />
      </div>

      <!-- Loading placeholder: keeps right pane pinned to the right while
           conversationsLoaded is false and no thread is active yet. Without
           this, the flex row has no flex-1 sibling and the pane shifts left. -->
      <div v-else key="loading" class="flex flex-1" />
    </Transition>

    <!-- Desktop right pane (Datasets) — shared across both states -->
    <template v-if="!isMobile">
      <div class="right-pane-handle" @mousedown="startRightResize" />
      <div
        class="shrink-0 border-l border-[var(--line)] overflow-hidden flex flex-col"
        :style="{ width: `${rightPaneWidth}px` }"
      >
        <ConversationInfoPanel />
      </div>
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
const router = useRouter()
const route = useRoute()

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
  if (chatStore.inputText.trim()) {
    handleSend()
  }
})

// ── View transition ───────────────────────────────────────
const isTransitioning = ref(false)
const sendingFromNewTask = ref(false)
const enterFromSend = ref(false)
const showNewTaskScreen = computed(() =>
  chatStore.conversationsLoaded &&
  !chatStore.currentThreadId &&
  !isTransitioning.value
)
watch(() => chatStore.currentThreadId, (id) => {
  if (!id) { isTransitioning.value = false; sendingFromNewTask.value = false }
  else if (route.path === '/chat' && route.query.id !== id) {
    router.replace({ path: '/chat', query: { id } })
  }
})

// ── Message handlers ──────────────────────────────────────
const handleSend = () => {
  if (chatStore.inputText.trim()) {
    const fileIds = getFileIds()
    if (!chatStore.currentThreadId) {
      // Add sidebar entry immediately so slide-in animation fires right away
      const tempId = `pending-${Date.now()}`
      chatStore.pendingNewConversationId = tempId
      chatStore.addConversation({
        id: tempId,
        title: chatStore.inputText.trim().substring(0, 80),
        type: 'task',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 1,
      })
      // Trigger in-place element animation; swap view after 0.5s (matches composer slide)
      sendingFromNewTask.value = true
      setTimeout(() => {
        enterFromSend.value = true   // suppress horizontal slide-in on chat view
        isTransitioning.value = true
        setTimeout(() => { sendingFromNewTask.value = false }, 30)
        setTimeout(() => { enterFromSend.value = false }, 280)  // after 0.25s fade-in
      }, 500)
    }
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
/* Standard horizontal page transition — matches global page-fade-slide
   (Bingo↔Dashboard). With mode="out-in" on the Transition, leave fully
   completes before enter starts, so position:absolute is unnecessary. */
.view-switch-leave-active,
.view-switch-enter-active { transition: opacity 0.3s ease-out; }
.view-switch-enter-from,
.view-switch-leave-to { opacity: 0; }

/* When sending from New Task: the New Task wrapper has already animated
   its contents internally — suppress the leave so there's no horizontal snap */
.new-task-sending.view-switch-leave-active { transition: none; }

/* Chat view appears INSTANTLY at full opacity at the moment the composer
   reaches the bottom — visual continuity: composer at bottom → swap →
   ChatInputBar at bottom (looks like the same element). The opacity:1 override
   is what stops the fade-in that previously read as "the text box faded away". */
.enter-from-send .view-switch-enter-active { transition: none; }
.enter-from-send .view-switch-enter-from   { opacity: 1; transform: none; }


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
