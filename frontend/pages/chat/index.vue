<template>
  <div class="flex flex-1 overflow-hidden relative">

    <!-- ── Stacked content area ──────────────────────────────── -->
    <!-- ChatThread underneath, HomeNewTaskScreen on top when New Task screen active.
         ChatInputBar rendered ONCE at container level — same element moves from center to bottom. -->
    <div
      class="relative flex-1 min-w-0 min-h-0 overflow-hidden"
      :class="{ 'composer-anchored': isComposerAnchored }"
      :style="{ '--composer-h': composerHeightPx }"
    >

      <!-- Chat layer — mounts when thread exists or transitioning -->
      <div
        v-if="chatStore.currentThreadId || isTransitioning"
        class="absolute left-0 right-0 top-0 flex flex-col z-0"
        :style="{ bottom: composerHeightPx }"
      >
        <div class="flex-1 min-h-0 overflow-hidden flex flex-col">
          <Transition :name="chatStore.currentThreadId ? 'page-fade-slide' : ''" mode="out-in">
            <ChatThread v-if="chatStore.currentThreadId || chatStore.messages.length > 0" :key="chatStore.currentThreadId ?? 'pending'" @send-action="handleAction" />
          </Transition>
        </div>
      </div>

      <!-- Briefing layer — opaque overlay, closes back to chat -->
      <Transition name="view-switch" mode="out-in">
        <div
          v-if="activeBriefingId"
          :key="'briefing-' + activeBriefingId"
          class="absolute inset-0 flex flex-col z-20 bg-[var(--paper-0)]"
        >
          <div class="flex items-center gap-2 px-4 py-2 border-b border-[var(--line)] flex-shrink-0">
            <button
              class="text-[12px] text-[var(--ink-2)] hover:text-[var(--ink-0)] flex items-center gap-1"
              @click="closeBriefing"
            >
              <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/></svg>
              Back to chat
            </button>
          </div>
          <div class="flex-1 overflow-y-auto">
            <ChatBriefingView :briefing-id="activeBriefingId" />
          </div>
        </div>
      </Transition>

      <!-- New Task layer — headings + sections only (no composer). -->
      <!-- Stays mounted during the 500ms slide so headings can fade out. -->
      <div
        v-if="(showNewTaskScreen || isTransitioning) && chatStore.messages.length === 0"
        class="absolute inset-0 flex flex-col z-10 overflow-y-auto new-task-layer"
      >
        <HomeNewTaskScreen :is-sending="isTransitioning" @send="handleSend" />
      </div>

      <!-- PAGE-LEVEL ChatInputBar — same element transitions between center and bottom -->
      <div
        ref="composerStageRef"
        v-if="(showNewTaskScreen || isTransitioning || chatStore.currentThreadId || chatStore.messages.length > 0) && !activeBriefingId"
        class="composer-stage absolute left-0 right-0 z-30"
        :class="composerStageClasses"
        :style="composerStageStyle"
      >
        <ChatInputBar @send="handleSend" @reset="handleReset" />
      </div>

    </div>

    <!-- Desktop right pane (Datasets) — shared across both states -->
    <template v-if="!isMobile && chatStore.infoPanelOpen && hasPaneContent">
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
        v-if="isMobile && chatStore.infoPanelOpen && hasPaneContent"
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
import { useElementSize } from '@vueuse/core'
import { useChatFileUpload } from '~/composables/useChatFileUpload'
import { useDatasetStatus } from '~/composables/useDatasetStatus'
import { useBriefingsList } from '~/composables/useBriefingsList'

const chatStore = useChatStore()
const chat = useChat()
const { getFileIds, clearFiles } = useChatFileUpload()
const { isMobile } = useIsMobile()
const router = useRouter()
const route = useRoute()

const { datasets } = useDatasetStatus()
const { briefings } = useBriefingsList()

const isPermanentThread = computed(() =>
  chatStore.currentThreadId === chatStore.permanentConversation?.id
)

const hasPaneContent = computed(() =>
  datasets.value.length > 0 ||
  (isPermanentThread.value && briefings.value.length > 0)
)

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
    chatStore.infoPanelOpen = hasPaneContent.value
  }
  if (chatStore.inputText.trim()) {
    handleSend()
  } else if (!chatStore.currentThreadId) {
    // Position ChatInputBar at center on the New Task screen
    nextTick(() => computeComposerCenter())
  }
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
})

watch(hasPaneContent, (now, prev) => {
  if (!prev && now && !isMobile.value) {
    chatStore.infoPanelOpen = true
  }
})

// ── View transition ───────────────────────────────────────
const isTransitioning = ref(false)
const showNewTaskScreen = computed(() =>
  chatStore.conversationsLoaded &&
  !chatStore.currentThreadId &&
  !isTransitioning.value
)
watch(() => chatStore.currentThreadId, (id) => {
  if (id) {
    isTransitioning.value = false
    composerSlideOffset.value = 0
    if (route.path === '/chat' && route.query.id !== id) {
      router.replace({ path: '/chat', query: { id } })
    }
  } else {
    // New Task screen — reposition composer to center
    nextTick(() => computeComposerCenter())
  }
})

// ── Composer stage (single ChatInputBar, center↔bottom slide) ──
const composerSlideOffset = ref(0)
const composerStageAnimating = ref(false)
const composerStageRef = ref<HTMLElement | null>(null)
const { height: composerMeasured } = useElementSize(composerStageRef, undefined, { box: 'border-box' })
const composerHeightPx = computed(() => {
  const h = composerMeasured.value
  return (h && h > 0 ? h : 220) + 'px'
})

// Re-center the floating composer when its height changes (e.g. file chip added/removed).
// Gated by isComposerAnchored so it only fires on the New Task screen.
watch(composerMeasured, () => {
  if (!isComposerAnchored.value) computeComposerCenter()
})

const isComposerAnchored = computed(() =>
  !!(chatStore.currentThreadId
  || isTransitioning.value
  || chatStore.isStreaming
  || chatStore.messages.length > 0)
)

const composerStageClasses = computed(() => ({
  'composer-stage--animating': composerStageAnimating.value,
}))

const composerStageStyle = computed(() => {
  if (composerSlideOffset.value === 0 && !composerStageAnimating.value) return undefined
  return { transform: `translateY(${composerSlideOffset.value}px)` }
})

// Compute the offset to position ChatInputBar below the hero subtitle.
// Falls back to vh * 0.38 when the subtitle isn't mounted yet.
const computeComposerCenter = () => {
  const vh = window.innerHeight
  let targetTop = vh * 0.38
  nextTick(() => {
    const stage = document.querySelector('.composer-stage') as HTMLElement | null
    if (!stage) return
    const heroSub = document.querySelector('.home-hero-sub') as HTMLElement | null
    if (heroSub) {
      const subBottom = heroSub.getBoundingClientRect().bottom
      targetTop = subBottom + 32
    }
    const stageHeight = stage.offsetHeight
    composerSlideOffset.value = targetTop - (vh - stageHeight)
  })
}

const onWindowResize = () => {
  if (!chatStore.currentThreadId && !isTransitioning.value) {
    computeComposerCenter()
  }
}

// ── Message handlers ──────────────────────────────────────
const handleSend = () => {
  if (!chatStore.inputText.trim()) return
  const fileIds = getFileIds()

  if (!chatStore.currentThreadId) {
    // Add sidebar entry immediately
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
    isTransitioning.value = true
    // Enable CSS transition on the composer stage
    composerStageAnimating.value = true
    // On next frame, remove the center offset → transitions to bottom (0)
    nextTick(() => {
      composerSlideOffset.value = 0
    })
    setTimeout(() => { composerStageAnimating.value = false }, 520)
  }

  chat.sendMessage(chatStore.inputText, fileIds)
  clearFiles()
}

const handleAction = (text: string, source?: string) => {
  if (!chatStore.isStreaming) {
    chat.sendMessage(text, [], source ? { source: source as any } : undefined)
  }
}

const handleReset = () => {
  chat.resetContext()
}

// ── Inline briefing view ──────────────────────────────────
const { id: activeBriefingId, close: closeBriefing } = useActiveBriefing()

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

/* New Task layer — no fade-out when unmounted (ChatThread underneath is already visible) */
.new-task-layer.view-switch-leave-active { transition: none; }

/* ── Composer stage — ChatInputBar slides from center to bottom ──────────── */
.composer-stage {
  bottom: 0;
}
.composer-stage--animating {
  transition: transform 0.5s ease-in;
}


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
