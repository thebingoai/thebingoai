<template>
  <aside class="flex w-sidebar flex-col border-r border-gray-200 bg-white">
    <!-- Logo -->
    <div class="flex h-16 items-center border-b border-gray-200 px-6">
      <component :is="MessageSquare" class="h-6 w-6 text-gray-900" />
      <span class="ml-3 text-lg font-normal text-gray-900">
        {{ chatStore.permanentConversation?.title || 'Bingo AI' }}
      </span>
    </div>

    <!-- Permanent conversation (pinned) -->
    <div v-if="chatStore.permanentConversation" class="border-b border-gray-100">
      <button
        @click="handleSelectConversation(chatStore.permanentConversation!.id)"
        class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors duration-200"
        :class="route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation.id ? 'bg-gray-100' : ''"
      >
        <span class="relative flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full">
          <span
            class="absolute inset-0 rounded-full bg-gradient-to-br from-orange-400 to-orange-500 transition-opacity duration-200"
            :class="route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation!.id ? 'opacity-100' : 'opacity-0'"
          />
          <Sparkles class="relative h-3.5 w-3.5 text-gray-900" />
        </span>
        <span
          class="flex-1 min-w-0 text-sm truncate"
          :class="route.path === '/chat' && chatStore.currentThreadId === chatStore.permanentConversation.id ? 'font-bold text-glow-orange' : 'font-light text-gray-900'"
        >
          {{ chatStore.permanentConversation.title || 'Bingo AI' }}
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
        @click="router.push('/dashboard')"
        class="flex w-full items-center gap-3 px-4 py-3 text-sm font-extralight text-gray-700 hover:bg-gray-100 transition-colors duration-200"
        :class="route.path === '/dashboard' ? 'bg-gray-100' : ''"
      >
        <span class="relative flex h-7 w-7 items-center justify-center rounded-full">
          <span
            class="absolute inset-0 rounded-full bg-gradient-to-br from-orange-400 to-orange-500 transition-opacity duration-200"
            :class="route.path === '/dashboard' ? 'opacity-100' : 'opacity-0'"
          />
          <LayoutDashboard class="relative h-3.5 w-3.5 text-gray-900" />
        </span>
        <span :class="route.path === '/dashboard' ? 'font-bold text-glow-orange' : ''">Dashboard</span>
      </button>
    </div>

    <!-- New Task Button -->
    <div>
      <button
        @click="handleNewTask"
        class="flex w-full items-center gap-3 px-4 py-3 text-sm font-extralight text-gray-700 hover:bg-gray-100 transition-colors duration-200"
        :class="route.path === '/chat' && !chatStore.currentThreadId ? 'bg-gray-100' : ''"
      >
        <span class="relative flex h-7 w-7 items-center justify-center rounded-full">
          <span
            class="absolute inset-0 rounded-full bg-gradient-to-br from-orange-400 to-orange-500 transition-opacity duration-200"
            :class="route.path === '/chat' && !chatStore.currentThreadId ? 'opacity-100' : 'opacity-0'"
          />
          <Plus class="relative h-3.5 w-3.5 text-gray-900" />
        </span>
        <span :class="route.path === '/chat' && !chatStore.currentThreadId ? 'font-bold text-glow-orange' : ''">New Task</span>
      </button>
    </div>

    <!-- Task conversation list -->
    <div class="flex-1 overflow-y-auto">
      <!-- Recent tasks section header -->
      <button
        @click="isRecentExpanded = !isRecentExpanded"
        class="flex w-full items-center gap-2 px-4 py-2 text-xs font-extralight uppercase tracking-wider text-gray-400 hover:text-gray-600"
      >
        <ChevronDown v-if="isRecentExpanded" class="h-3.5 w-3.5" />
        <ChevronRight v-else class="h-3.5 w-3.5" />
        Recent Tasks
      </button>

      <!-- Task list (collapsible) -->
      <div v-show="isRecentExpanded">
        <div v-if="chatStore.taskConversations.length === 0" class="px-4 py-4 text-center text-sm text-gray-500">
          No tasks yet
        </div>
        <template v-for="group in groupedTasks" :key="group.label">
          <div class="px-4 pt-4 text-[11px] text-gray-800">{{ group.label }}</div>
          <button
            v-for="conv in group.conversations"
            :key="conv.id"
            @click="handleSelectConversation(conv.id)"
            class="w-full px-4 py-2 text-left text-sm hover:bg-gray-50"
            :class="chatStore.currentThreadId === conv.id ? 'bg-gray-50' : ''"
          >
            <div
              class="truncate"
              :class="chatStore.currentThreadId === conv.id ? 'font-bold text-glow-orange ' : 'font-extralight text-gray-500'"
            >{{ conv.title }}</div>
          </button>
        </template>
      </div>
    </div>

    <!-- User account button -->
    <button
      @click="router.push('/settings')"
      class="border-t border-gray-200 px-4 pb-6 pt-5 hover:bg-gray-50 transition-colors w-full text-left"
    >
      <div class="flex items-center">
        <div class="flex h-10 w-10 items-center justify-center rounded-full bg-gray-900 text-white text-sm font-light">
          {{ userInitial }}
        </div>
        <div class="ml-3 flex-1 min-w-0">
          <p class="text-sm font-light text-gray-900 truncate">{{ authStore.user?.email }}</p>
          <p class="text-xs text-gray-500">View settings</p>
        </div>
        <component :is="Settings" class="h-4 w-4 text-gray-400" />
      </div>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { MessageSquare, Settings, Plus, ChevronDown, ChevronRight, Sparkles, LayoutDashboard } from 'lucide-vue-next'
import { formatDateLabel } from '~/utils/format'
import type { Conversation } from '~/stores/chat'

const authStore = useAuthStore()
const chatStore = useChatStore()
const chat = useChat()
const router = useRouter()
const route = useRoute()

const groupedTasks = computed(() => {
  const groups: { label: string; conversations: Conversation[] }[] = []
  let currentLabel = ''
  for (const conv of chatStore.taskConversations) {
    const label = formatDateLabel(new Date(conv.updated_at))
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

const userInitial = computed(() => {
  const email = authStore.user?.email || ''
  return email.charAt(0).toUpperCase()
})

// Load conversations on mount and register heartbeat handler
onMounted(() => {
  chatStore.hydrateFromStorage()
  chat.loadConversations()
  chat.registerHeartbeatHandler()
})

const handleNewTask = () => {
  chat.newChat()
  if (route.path !== '/chat') {
    navigateTo('/chat')
  }
}

const handleSelectConversation = (id: string) => {
  // Clear unread when opening the conversation
  chatStore.clearUnread(id)
  chat.loadMessages(id)
  if (route.path !== '/chat') {
    navigateTo('/chat')
  }
}
</script>
