<template>
  <!-- Desktop sidebar -->
  <aside
    v-if="!isMobile"
    class="flex flex-col border-r border-[var(--line)] bg-[var(--paper-1)] transition-[width] duration-200 ease-in-out flex-shrink-0 overflow-hidden"
    :style="{ width: layoutStore.sidebarCollapsed ? '56px' : `${layoutStore.sidebarWidth}px` }"
  >
    <!-- ── EXPANDED state ─────────────────────────────────── -->
    <template v-if="!layoutStore.sidebarCollapsed">
      <!-- Logo row + collapse button -->
      <div class="flex h-14 items-center px-4 gap-2 flex-shrink-0">
        <img src="/logo/BINGO Logo Design_FA_Primary.png" alt="Bingo" style="height: 24px; width: auto;" class="dark:hidden" />
        <img src="/logo/BINGO Logo Design_FA_Primary_W.png" alt="Bingo" style="height: 24px; width: auto;" class="hidden dark:block" />
        <div class="flex-1" />
        <button
          @click="layoutStore.toggleSidebarCollapsed()"
          class="flex h-6 w-6 items-center justify-center rounded text-[var(--ink-3)] hover:text-[var(--ink-1)] hover:bg-[var(--paper-3)] transition-colors flex-shrink-0"
          title="Collapse sidebar"
        >
          <PanelLeftClose class="h-3.5 w-3.5" />
        </button>
      </div>

      <!-- Permanent conversation (Bingo personal assistant) -->
      <div v-if="chatStore.permanentConversation">
        <button
          @click="handleSelectConversation(chatStore.permanentConversation!.id)"
          class="flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors duration-150 border-l-2"
          :class="isPermActive ? 'border-[var(--ember)] bg-[var(--ember-wash)]' : 'border-transparent hover:bg-[var(--paper-2)]'"
        >
          <span class="flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-md"
            :class="isPermActive ? 'text-[var(--ember)]' : 'text-[var(--ink-1)]'"
          >
            <Sparkles class="h-3.5 w-3.5" />
          </span>
          <div class="flex-1 min-w-0">
            <div
              class="sidebar-title text-[13px] tracking-[-0.005em] truncate"
              :class="isPermActive ? 'font-semibold text-[var(--ink-0)] text-glow-orange' : 'font-medium text-[var(--ink-0)]'"
            >
              <span class="marquee-inner">
                <span>{{ chatStore.permanentConversation.title || 'Bingo' }}</span>
                <span class="marquee-spacer">&nbsp;&mdash;&nbsp;</span>
                <span>{{ chatStore.permanentConversation.title || 'Bingo' }}</span>
              </span>
            </div>
            <div class="text-[10.5px] text-[var(--ink-2)] mt-0.5">personal assistant</div>
          </div>
          <span
            v-if="chatStore.permanentConversation.unread_count && chatStore.permanentConversation.unread_count > 0"
            class="flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-[var(--ink-0)] px-1 text-[10px] font-medium text-[var(--paper-0)]"
          >
            {{ chatStore.permanentConversation.unread_count > 99 ? '99+' : chatStore.permanentConversation.unread_count }}
          </span>
        </button>
      </div>

      <!-- Dashboards -->
      <button
        @click="router.push('/dashboard'); closeSidebarOnMobile()"
        class="flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors duration-150 border-l-2"
        :class="route.path === '/dashboard' ? 'border-[var(--ember)] bg-[var(--ember-wash)]' : 'border-transparent hover:bg-[var(--paper-2)]'"
      >
        <span class="flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-md"
          :class="route.path === '/dashboard' ? 'text-[var(--ember)]' : 'text-[var(--ink-1)]'"
        >
          <LayoutDashboard class="h-3.5 w-3.5" />
        </span>
        <span
          class="text-[13px] tracking-[-0.005em]"
          :class="route.path === '/dashboard' ? 'font-semibold text-[var(--ink-0)]' : 'font-medium text-[var(--ink-0)]'"
        >Dashboards</span>
      </button>

      <!-- New Task -->
      <button
        @click="handleNewTask"
        class="flex w-full items-center gap-2.5 px-4 py-2.5 text-left transition-colors duration-150 border-l-2"
        :class="isNewTaskActive ? 'border-[var(--ember)] bg-[var(--ember-wash)]' : 'border-transparent hover:bg-[var(--paper-2)]'"
      >
        <span class="flex h-[22px] w-[22px] flex-shrink-0 items-center justify-center rounded-md"
          :class="isNewTaskActive ? 'text-[var(--ember)]' : 'text-[var(--ink-2)]'"
        >
          <Plus class="h-3.5 w-3.5" />
        </span>
        <span
          class="text-[13px] tracking-[-0.005em]"
          :class="isNewTaskActive ? 'font-semibold text-[var(--ink-0)]' : 'font-medium text-[var(--ink-1)]'"
        >New task</span>
      </button>

      <!-- Recent tasks label -->
      <div class="flex items-center justify-between px-4 pt-3.5 pb-1.5 flex-shrink-0">
        <button
          @click="isRecentExpanded = !isRecentExpanded"
          class="eyebrow flex items-center gap-1 hover:text-[var(--ink-1)] transition-colors"
        >
          <ChevronDown v-if="isRecentExpanded" class="h-3 w-3" />
          <ChevronRight v-else class="h-3 w-3" />
          Recent tasks
        </button>
        <span class="font-mono text-[10px] text-[var(--ink-3)]">{{ chatStore.taskConversations.length }}</span>
      </div>

      <!-- Task list -->
      <div ref="taskListRef" class="flex-1 overflow-y-auto pb-2 min-h-0" @scroll="onTaskListScroll">
        <div v-show="isRecentExpanded">
          <div v-if="chatStore.taskConversations.length === 0" class="px-4 py-3 text-[12px] text-[var(--ink-3)]">
            No tasks yet
          </div>
          <template v-for="group in groupedTasks" :key="group.label">
            <div class="px-4 pt-3 pb-1 eyebrow">{{ group.label }}</div>
            <button
              v-for="conv in group.conversations"
              :key="conv.id"
              @click="handleSelectConversation(conv.id)"
              class="w-full flex items-baseline gap-2 px-4 py-1.5 text-left transition-colors duration-150 border-l-2"
              :class="[
                chatStore.currentThreadId === conv.id
                  ? 'border-[var(--ember)] bg-[var(--ember-wash)]'
                  : 'border-transparent hover:bg-[var(--paper-2)]',
                conv.id === newlyAddedId ? 'task-slide-in' : ''
              ]"
            >
              <span
                class="sidebar-title flex-1 min-w-0 text-[12.5px] overflow-hidden text-ellipsis whitespace-nowrap"
                :class="chatStore.currentThreadId === conv.id ? 'font-semibold text-[var(--ink-0)]' : 'font-normal text-[var(--ink-1)]'"
              >
                <span class="marquee-inner">
                  <span>{{ conv.title }}</span>
                  <span class="marquee-spacer">&nbsp;&mdash;&nbsp;</span>
                  <span>{{ conv.title }}</span>
                </span>
              </span>
            </button>
          </template>
          <div v-if="chatStore.isLoadingMoreConversations" class="px-4 py-2 text-[11px] text-[var(--ink-3)]">
            Loading…
          </div>
        </div>
      </div>

      <!-- Archived -->
      <div class="border-t border-dashed border-[var(--line-2)] px-4 py-2.5 flex-shrink-0">
        <button
          @click="handleToggleArchived"
          class="eyebrow flex items-center gap-1.5 hover:text-[var(--ink-1)] transition-colors"
        >
          <ArchiveIcon class="h-3 w-3" />
          Archived
        </button>
        <div v-show="isArchivedExpanded" class="mt-1 max-h-48 overflow-y-auto">
          <div v-if="chatStore.archivedConversations.length === 0" class="py-2 text-[11px] text-[var(--ink-3)]">
            No archived tasks
          </div>
          <div
            v-for="conv in chatStore.archivedConversations"
            :key="conv.id"
            class="group flex w-full items-center py-1 rounded-md px-1 -mx-1 hover:bg-[var(--paper-2)]"
          >
            <button @click="handleSelectConversation(conv.id)" class="flex-1 min-w-0 truncate text-[12px] text-[var(--ink-1)] text-left">
              {{ conv.title }}
            </button>
            <button
              @click.stop="handleUnarchive(conv.id)"
              class="ml-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-[var(--paper-3)]"
              aria-label="Unarchive"
            >
              <ArchiveRestore class="h-3 w-3 text-[var(--ink-3)]" />
            </button>
          </div>
        </div>
      </div>

      <!-- Account block -->
      <button
        @click="router.push('/settings'); closeSidebarOnMobile()"
        class="border-t border-[var(--line)] bg-[var(--paper-0)] px-[18px] py-3.5 hover:bg-[var(--paper-1)] transition-colors w-full text-left flex-shrink-0"
      >
        <div class="flex items-center gap-2.5">
          <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--ink-0)] text-[var(--paper-0)] text-[12px] font-semibold">
            {{ userInitial }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-[12.5px] font-medium text-[var(--ink-0)] truncate">{{ authStore.user?.email }}</p>
            <p v-if="featureConfig?.credits_enabled !== false" class="font-mono text-[11px] text-[var(--ink-2)]">
              <span class="text-[var(--ember)]">●</span> {{ Math.round(remaining) }} credits
            </p>
          </div>
          <component :is="Settings" class="h-3.5 w-3.5 text-[var(--ink-2)]" />
        </div>
      </button>

    </template>

    <!-- ── COLLAPSED state (56px icon rail) ──────────────── -->
    <template v-else>

      <!-- Logo / expand button -->
      <div
        class="flex h-14 items-center justify-center flex-shrink-0 group cursor-pointer"
        @click="layoutStore.toggleSidebarCollapsed()"
        title="Open sidebar"
      >
        <!-- Logo visible by default, swap to expand icon on hover -->
        <img src="/logo/BINGO Logo Design_FA_Primary.png" alt="Bingo" style="height: 24px; width: auto;" class="hidden dark:block group-hover:hidden" />
        <img src="/logo/BINGO Logo Design_FA_Primary_W.png" alt="Bingo" style="height: 24px; width: auto;" class="hidden dark:block group-hover:hidden" />
        <PanelLeftOpen class="h-4 w-4 text-[var(--ink-2)] hidden group-hover:block" />
      </div>

      <!-- Bingo (permanent chat) icon -->
      <button
        v-if="chatStore.permanentConversation"
        @click="handleSelectConversation(chatStore.permanentConversation!.id)"
        class="flex h-10 w-full items-center justify-center transition-colors border-l-2"
        :class="isPermActive ? 'border-[var(--ember)] bg-[var(--ember-wash)] text-[var(--ember)]' : 'border-transparent hover:bg-[var(--paper-2)] text-[var(--ink-1)]'"
        title="Bingo – personal assistant"
      >
        <Sparkles class="h-4 w-4" />
      </button>

      <!-- Dashboards icon -->
      <button
        @click="router.push('/dashboard')"
        class="flex h-10 w-full items-center justify-center transition-colors border-l-2"
        :class="route.path === '/dashboard' ? 'border-[var(--ember)] bg-[var(--ember-wash)] text-[var(--ember)]' : 'border-transparent hover:bg-[var(--paper-2)] text-[var(--ink-1)]'"
        title="Dashboards"
      >
        <LayoutDashboard class="h-4 w-4" />
      </button>

      <!-- New Task icon -->
      <button
        @click="handleNewTask"
        class="flex h-10 w-full items-center justify-center transition-colors border-l-2"
        :class="isNewTaskActive ? 'border-[var(--ember)] bg-[var(--ember-wash)] text-[var(--ember)]' : 'border-transparent hover:bg-[var(--paper-2)] text-[var(--ink-2)]'"
        title="New task"
      >
        <Plus class="h-4 w-4" />
      </button>

      <!-- Spacer -->
      <div class="flex-1" />

      <!-- User account icon -->
      <button
        @click="router.push('/settings')"
        class="flex h-12 w-full items-center justify-center border-t border-[var(--line)] bg-[var(--paper-0)] hover:bg-[var(--paper-1)] transition-colors flex-shrink-0"
        :title="featureConfig?.credits_enabled !== false ? `${Math.round(remaining)} credits` : 'Settings'"
      >
        <div class="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--ink-0)] text-[var(--paper-0)] text-[11px] font-semibold">
          {{ userInitial }}
        </div>
      </button>

    </template>
  </aside>

  <!-- Mobile sidebar (fixed overlay) -->
  <aside
    v-if="isMobile"
    class="fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[var(--line)] bg-[var(--paper-1)] transition-transform duration-300"
    :class="{ '-translate-x-full pointer-events-none': layoutStore.isMainExpanded }"
    style="width: 220px"
  >
    <div class="flex h-14 items-center px-4">
      <img src="/logo/BINGO Logo Design_FA_Primary.png" alt="Bingo" style="height: 36px; width: auto;" class="hidden dark:block" />
      <img src="/logo/BINGO Logo Design_FA_Primary_W.png" alt="Bingo" style="height: 36px; width: auto;" class="hidden dark:block" />
      <div class="flex-1" />
      <button @click="layoutStore.setMainExpanded(true)" class="p-1 text-[var(--ink-3)] hover:text-[var(--ink-1)]">
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Mobile nav items (same as expanded desktop) -->
    <div v-if="chatStore.permanentConversation">
      <button
        @click="handleSelectConversation(chatStore.permanentConversation!.id)"
        class="flex w-full items-center gap-2.5 px-4 py-2.5 border-l-2"
        :class="isPermActive ? 'border-[var(--ember)] bg-[var(--ember-wash)]' : 'border-transparent hover:bg-[var(--paper-2)]'"
      >
        <Sparkles class="h-3.5 w-3.5 flex-shrink-0" :class="isPermActive ? 'text-[var(--ember)]' : 'text-[var(--ink-1)]'" />
        <span class="text-[13px] font-medium text-[var(--ink-0)] truncate">{{ chatStore.permanentConversation.title || 'Bingo' }}</span>
      </button>
    </div>
    <button @click="router.push('/dashboard'); closeSidebarOnMobile()" class="flex w-full items-center gap-2.5 px-4 py-2.5 border-l-2 border-transparent hover:bg-[var(--paper-2)]">
      <LayoutDashboard class="h-3.5 w-3.5 text-[var(--ink-1)]" />
      <span class="text-[13px] font-medium text-[var(--ink-0)]">Dashboards</span>
    </button>
    <button @click="handleNewTask" class="flex w-full items-center gap-2.5 px-4 py-2.5 border-l-2 border-transparent hover:bg-[var(--paper-2)]">
      <Plus class="h-3.5 w-3.5 text-[var(--ink-2)]" />
      <span class="text-[13px] font-medium text-[var(--ink-1)]">New task</span>
    </button>

    <div class="flex-1 overflow-y-auto px-2 py-2">
      <template v-for="conv in chatStore.taskConversations" :key="conv.id">
        <button @click="handleSelectConversation(conv.id)" class="w-full text-left px-2 py-1.5 text-[12.5px] text-[var(--ink-1)] hover:bg-[var(--paper-2)] rounded-md truncate">
          {{ conv.title }}
        </button>
      </template>
    </div>

    <button @click="router.push('/settings'); closeSidebarOnMobile()" class="border-t border-[var(--line)] px-4 py-3 flex items-center gap-2.5 hover:bg-[var(--paper-1)]">
      <div class="h-8 w-8 rounded-full bg-[var(--ink-0)] text-[var(--paper-0)] flex items-center justify-center text-[12px] font-semibold flex-shrink-0">{{ userInitial }}</div>
      <div class="min-w-0">
        <span class="text-[12.5px] text-[var(--ink-0)] truncate block">{{ authStore.user?.email }}</span>
        <span v-if="featureConfig?.credits_enabled !== false" class="font-mono text-[10px] text-[var(--ink-2)]">
          <span class="text-[var(--ember)]">●</span> {{ Math.round(remaining) }} credits
        </span>
      </div>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { Settings, Plus, ChevronDown, ChevronRight, Sparkles, LayoutDashboard, Archive as ArchiveIcon, ArchiveRestore, PanelLeftClose, PanelLeftOpen, X } from 'lucide-vue-next'
import { formatDateLabel } from '~/utils/format'
import type { Conversation } from '~/stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()
const { remaining } = useCreditBalance()
const { config: featureConfig } = useFeatureConfig()
const layoutStore = useLayoutStore()

const chat = useChat()
const router = useRouter()
const route = useRoute()
const { isMobile } = useIsMobile()

const closeSidebarOnMobile = () => {
  if (isMobile.value) layoutStore.setMainExpanded(true)
}

const isPermActive = computed(() =>
  route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation?.id
)
const isNewTaskActive = computed(() =>
  route.path === '/chat' && !chatStore.currentThreadId
)

const groupedTasks = computed(() => {
  const groups: { label: string; conversations: Conversation[] }[] = []
  let currentLabel = ''
  for (const conv of chatStore.taskConversations) {
    const label = formatDateLabel(conv.updated_at)
    if (label !== currentLabel) {
      groups.push({ label, conversations: [conv] })
      currentLabel = label
    } else {
      groups[groups.length - 1].conversations.push(conv)
    }
  }
  return groups
})

const isRecentExpanded = ref(true)
const isArchivedExpanded = ref(false)
const newlyAddedId = ref<string | null>(null)

watch(
  () => chatStore.taskConversations[0]?.id,
  (newId, oldId) => {
    if (newId && newId !== oldId) {
      // Skip re-animation when the pending placeholder is silently replaced by the real thread ID
      if (oldId?.startsWith('pending-')) return
      newlyAddedId.value = newId
      setTimeout(() => { newlyAddedId.value = null }, 500)
    }
  },
  { flush: 'post' }
)
const archivedLoaded = ref(false)
const taskListRef = ref<HTMLElement | null>(null)

const onTaskListScroll = () => {
  const el = taskListRef.value
  if (!el) return
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 100) {
    chat.loadMoreConversations()
  }
}

const userInitial = computed(() => {
  const email = authStore.user?.email || ''
  return email.charAt(0).toUpperCase()
})

onMounted(() => {
  const urlId = route.query.id as string | undefined
  if (urlId) {
    chatStore.currentThreadId = urlId
  } else {
    chatStore.hydrateFromStorage()
  }
  if (!chatStore.conversationsLoaded) {
    chat.loadConversations()
  }
  chat.registerTitleHandler()
  chat.registerSummaryHandler()
  chat.registerHeartbeatHandler()
  chat.registerSkillSuggestionsHandler()
  chat.registerTelegramHandler()

  const api = useApi()
  api.skills.listSuggestions()
    .then((suggestions: any) => {
      if (Array.isArray(suggestions) && suggestions.length > 0) {
        chatStore.setSkillSuggestions(suggestions)
      }
    })
    .catch(() => {})
})

const handleNewTask = () => {
  chat.newChat()
  if (route.path !== '/chat') navigateTo('/chat')
  closeSidebarOnMobile()
}

const handleToggleArchived = () => {
  isArchivedExpanded.value = !isArchivedExpanded.value
  if (isArchivedExpanded.value && !archivedLoaded.value) {
    chat.loadArchivedConversations()
    archivedLoaded.value = true
  }
}

const handleUnarchive = (threadId: string) => {
  chat.unarchiveConversation(threadId)
}

const handleSelectConversation = (id: string) => {
  chatStore.clearUnread(id)
  chat.loadMessages(id)
  if (route.path !== '/chat') navigateTo('/chat')
  closeSidebarOnMobile()
}
</script>

<style scoped>
@keyframes taskSlideIn {
  from { opacity: 0; transform: translateX(-14px); }
  to   { opacity: 1; transform: translateX(0); }
}
.task-slide-in {
  animation: taskSlideIn 0.35s ease forwards;
}

.sidebar-title {
  overflow: hidden;
  white-space: nowrap;
}
.marquee-inner {
  display: inline-block;
  white-space: nowrap;
}
.marquee-spacer,
.marquee-inner > span:last-child {
  display: none;
}
.sidebar-title:hover .marquee-spacer,
.sidebar-title:hover .marquee-inner > span:last-child {
  display: inline;
}
.sidebar-title:hover .marquee-inner {
  animation: marquee-scroll 8s linear infinite;
}
@keyframes marquee-scroll {
  0%   { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
</style>

<style>
.sidebar-title.text-glow-orange:hover {
  background: none !important;
  -webkit-text-fill-color: unset !important;
}
.sidebar-title.text-glow-orange:hover .marquee-inner {
  background: linear-gradient(90deg, #6E489D, #AE86BC, #DAC7E1, #AE86BC, #6E489D);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
</style>
