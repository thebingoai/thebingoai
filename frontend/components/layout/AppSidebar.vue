<template>
  <aside
    class="flex w-sidebar flex-col border-r border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 transition-transform duration-300"
    :class="{
      'fixed inset-y-0 left-0 z-40': isMobile,
      '-translate-x-full pointer-events-none': isMobile && layoutStore.isMainExpanded,
    }"
  >
    <!-- Logo -->
    <div class="flex h-16 items-center border-b border-gray-200 dark:border-neutral-800 pl-[14px] pr-4">
      <img :src="'/logo/Bingo_BL.png'" alt="Bingo" class="h-16 w-auto dark:hidden" />
      <img :src="'/logo/Bingo_WH.png'" alt="Bingo" class="h-16 w-auto hidden dark:block" />
    </div>

    <!-- Permanent conversation (pinned) -->
    <div v-if="chatStore.permanentConversation" class="border-b border-gray-100 dark:border-neutral-800">
      <button
        @click="handleSelectConversation(chatStore.permanentConversation!.id)"
        class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors duration-200"
        :class="route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation.id ? 'bg-gray-100 dark:bg-neutral-800' : ''"
      >
        <span class="relative flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full">
          <span
            class="absolute inset-0 rounded-full bg-gradient-to-br from-orange-400 to-orange-500 transition-opacity duration-200"
            :class="route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation!.id ? 'opacity-100' : 'opacity-0'"
          />
          <Sparkles class="relative h-3.5 w-3.5 text-gray-900 dark:text-neutral-300" />
        </span>
        <span
          class="sidebar-title flex-1 min-w-0 text-sm"
          :class="route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation.id ? 'font-bold text-glow-orange' : 'font-light text-gray-900 dark:text-neutral-200'"

        >
          <span class="marquee-inner"><span>{{ chatStore.permanentConversation.title || 'Bingo AI' }}</span><span class="marquee-spacer">&nbsp;&mdash;&nbsp;</span><span>{{ chatStore.permanentConversation.title || 'Bingo AI' }}</span></span>
        </span>
        <!-- Unread badge -->
        <span
          v-if="chatStore.permanentConversation.unread_count && chatStore.permanentConversation.unread_count > 0"
          class="flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-gray-900 px-1.5 text-[10px] font-medium text-white"
        >
          {{ chatStore.permanentConversation.unread_count > 99 ? '99+' : chatStore.permanentConversation.unread_count }}
        </span>
      </button>
    </div>

    <!-- Dashboard link -->
    <div>
      <button
        @click="router.push('/dashboard'); closeSidebarOnMobile()"
        class="flex w-full items-center gap-3 px-4 py-3 text-sm font-extralight text-gray-700 dark:text-neutral-300 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors duration-200"
        :class="route.path === '/dashboard' ? 'bg-gray-100 dark:bg-neutral-800' : ''"
      >
        <span class="relative flex h-7 w-7 items-center justify-center rounded-full">
          <span
            class="absolute inset-0 rounded-full bg-gradient-to-br from-orange-400 to-orange-500 transition-opacity duration-200"
            :class="route.path === '/dashboard' ? 'opacity-100' : 'opacity-0'"
          />
          <LayoutDashboard class="relative h-3.5 w-3.5 text-gray-900 dark:text-neutral-300" />
        </span>
        <span :class="route.path === '/dashboard' ? 'font-bold text-glow-orange' : ''">Dashboard</span>
      </button>
    </div>

    <!-- New Task Button -->
    <div>
      <button
        @click="handleNewTask"
        class="flex w-full items-center gap-3 px-4 py-3 text-sm font-extralight text-gray-700 dark:text-neutral-300 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors duration-200"
        :class="route.path === '/chat' && !chatStore.currentThreadId ? 'bg-gray-100 dark:bg-neutral-800' : ''"
      >
        <span class="relative flex h-7 w-7 items-center justify-center rounded-full">
          <span
            class="absolute inset-0 rounded-full bg-gradient-to-br from-orange-400 to-orange-500 transition-opacity duration-200"
            :class="route.path === '/chat' && !chatStore.currentThreadId ? 'opacity-100' : 'opacity-0'"
          />
          <Plus class="relative h-3.5 w-3.5 text-gray-900 dark:text-neutral-300" />
        </span>
        <span :class="route.path === '/chat' && !chatStore.currentThreadId ? 'font-bold text-glow-orange' : ''">New Task</span>
      </button>
    </div>

    <!-- Task conversation list -->
    <div ref="taskListRef" class="flex-1 overflow-y-auto" @scroll="onTaskListScroll">
      <!-- Recent tasks section header -->
      <button
        @click="isRecentExpanded = !isRecentExpanded"
        class="flex w-full items-center gap-2 px-4 py-2 text-xs font-extralight uppercase tracking-wider text-gray-400 dark:text-neutral-300 hover:text-gray-600 dark:hover:text-neutral-100"
      >
        <ChevronDown v-if="isRecentExpanded" class="h-3.5 w-3.5" />
        <ChevronRight v-else class="h-3.5 w-3.5" />
        Recent Tasks
      </button>

      <!-- Task list (collapsible) -->
      <div v-show="isRecentExpanded">
        <div v-if="chatStore.taskConversations.length === 0" class="px-4 py-4 text-center text-sm text-gray-500 dark:text-neutral-500">
          No tasks yet
        </div>
        <template v-for="group in groupedTasks" :key="group.label">
          <div class="px-4 pt-4 text-[11px] text-gray-800 dark:text-neutral-300">{{ group.label }}</div>
          <button
            v-for="conv in group.conversations"
            :key="conv.id"
            @click="handleSelectConversation(conv.id)"
            class="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-neutral-800"
            :class="chatStore.currentThreadId === conv.id ? 'bg-gray-50 dark:bg-neutral-800' : ''"
          >
            <div
              class="sidebar-title"
              :class="chatStore.currentThreadId === conv.id ? 'font-bold text-glow-orange ' : 'font-extralight text-gray-500 dark:text-neutral-300'"

            ><span class="marquee-inner"><span>{{ conv.title }}</span><span class="marquee-spacer">&nbsp;&mdash;&nbsp;</span><span>{{ conv.title }}</span></span></div>
          </button>
        </template>

        <!-- Loading indicator for infinite scroll -->
        <div v-if="chatStore.isLoadingMoreConversations" class="px-4 py-3 text-center text-xs text-gray-400 dark:text-neutral-500">
          Loading more...
        </div>
      </div>

    </div>

    <!-- Archived section (pinned above user button) -->
    <div class="border-t border-gray-100 dark:border-neutral-800">
      <button
        @click="handleToggleArchived"
        class="flex w-full items-center gap-2 px-4 py-2 text-xs font-extralight uppercase tracking-wider text-gray-400 dark:text-neutral-300 hover:text-gray-600 dark:hover:text-neutral-100"
      >
        <ChevronDown v-if="isArchivedExpanded" class="h-3.5 w-3.5" />
        <ChevronRight v-else class="h-3.5 w-3.5" />
        <ArchiveIcon class="h-3 w-3" />
        Archived
      </button>

      <div v-show="isArchivedExpanded" class="max-h-48 overflow-y-auto">
        <div v-if="chatStore.archivedConversations.length === 0" class="px-4 py-4 text-center text-sm text-gray-500 dark:text-neutral-500">
          No archived tasks
        </div>
        <div
          v-for="conv in chatStore.archivedConversations"
          :key="conv.id"
          class="group flex w-full items-center px-4 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-neutral-800"
          :class="chatStore.currentThreadId === conv.id ? 'bg-gray-50 dark:bg-neutral-800' : ''"
        >
          <button
            @click="handleSelectConversation(conv.id)"
            class="flex-1 min-w-0"
          >
            <div
              class="sidebar-title"
              :class="chatStore.currentThreadId === conv.id ? 'font-bold text-glow-orange' : 'font-extralight text-gray-500'"

            ><span class="marquee-inner"><span>{{ conv.title }}</span><span class="marquee-spacer">&nbsp;&mdash;&nbsp;</span><span>{{ conv.title }}</span></span></div>
          </button>
          <button
            @click.stop="handleUnarchive(conv.id)"
            class="ml-2 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-gray-200 dark:hover:bg-neutral-700"
            aria-label="Unarchive conversation"
          >
            <ArchiveRestore class="h-3.5 w-3.5 text-gray-400 hover:text-gray-600" />
          </button>
        </div>
      </div>
    </div>

    <!-- User account button -->
    <button
      @click="router.push('/settings'); closeSidebarOnMobile()"
      class="border-t border-gray-200 dark:border-neutral-800 px-4 pb-6 pt-5 hover:bg-gray-50 dark:hover:bg-neutral-800 transition-colors w-full text-left"
    >
      <div class="flex items-center">
        <div class="flex h-10 w-10 items-center justify-center rounded-full bg-gray-900 text-white text-sm font-light">
          {{ userInitial }}
        </div>
        <div class="ml-3 flex-1 min-w-0">
          <p class="text-sm font-light text-gray-900 dark:text-neutral-200 truncate">{{ authStore.user?.email }}</p>
          <p
            v-if="featureConfig?.credits_enabled !== false"
            class="text-xs text-gray-400 dark:text-neutral-500 tabular-nums"
          >{{ Math.round(remaining) }} credits</p>
        </div>
        <component :is="Settings" class="h-4 w-4 text-gray-400" />
      </div>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { Settings, Plus, ChevronDown, ChevronRight, Sparkles, LayoutDashboard, Archive as ArchiveIcon, ArchiveRestore } from 'lucide-vue-next'
import { formatDateLabel } from '~/utils/format'
import type { Conversation } from '~/stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()
const { remaining, dailyLimit } = useCreditBalance()
const { config: featureConfig } = useFeatureConfig()
const layoutStore = useLayoutStore()

const chat = useChat()
const router = useRouter()
const route = useRoute()
const { isMobile } = useIsMobile()

const closeSidebarOnMobile = () => {
  if (isMobile.value) {
    layoutStore.setMainExpanded(true)
  }
}

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

// Load conversations on mount and register heartbeat handler
onMounted(() => {
  chatStore.hydrateFromStorage()
  // Only fetch conversations if not already loaded this session
  if (!chatStore.conversationsLoaded) {
    chat.loadConversations()
  }
  chat.registerTitleHandler()
  chat.registerSummaryHandler()
  chat.registerHeartbeatHandler()
  chat.registerSkillSuggestionsHandler()
  chat.registerTelegramHandler()

  // Fetch pending skill suggestions for side panel (catches missed WS pushes)
  const api = useApi()
  api.skills.listSuggestions()
    .then((suggestions: any) => {
      if (Array.isArray(suggestions) && suggestions.length > 0) {
        chatStore.setSkillSuggestions(suggestions)
      }
    })
    .catch(() => { /* non-critical */ })
})

const handleNewTask = () => {
  chat.newChat()
  if (route.path !== '/chat') {
    navigateTo('/chat')
  }
  closeSidebarOnMobile()
}

const handleToggleArchived = () => {
  isArchivedExpanded.value = !isArchivedExpanded.value
  // Lazy load archived conversations on first expand
  if (isArchivedExpanded.value && !archivedLoaded.value) {
    chat.loadArchivedConversations()
    archivedLoaded.value = true
  }
}

const handleUnarchive = (threadId: string) => {
  chat.unarchiveConversation(threadId)
}

const handleSelectConversation = (id: string) => {
  // Clear unread when opening the conversation
  chatStore.clearUnread(id)
  chat.loadMessages(id)
  if (route.path !== '/chat') {
    navigateTo('/chat')
  }
  closeSidebarOnMobile()
}
</script>

<style scoped>
.sidebar-title {
  overflow: hidden;
  white-space: nowrap;
}

.marquee-inner {
  display: inline-block;
  white-space: nowrap;
}

/* Hide the duplicate text + spacer by default */
.marquee-spacer,
.marquee-inner > span:last-child {
  display: none;
}

/* On hover: show duplicate and animate */
.sidebar-title:hover .marquee-spacer,
.sidebar-title:hover .marquee-inner > span:last-child {
  display: inline;
}

.sidebar-title:hover .marquee-inner {
  animation: marquee-scroll 8s linear infinite;
}

@keyframes marquee-scroll {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}
</style>

<style>
/* Active+hover: move gradient from parent to marquee-inner so it translates with text */
.sidebar-title.text-glow-orange:hover {
  background: none !important;
  -webkit-text-fill-color: unset !important;
}

.sidebar-title.text-glow-orange:hover .marquee-inner {
  background: linear-gradient(90deg, #f97316, #fb923c, #fdba74, #fb923c, #f97316);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
</style>
