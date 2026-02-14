<template>
  <aside class="flex w-sidebar flex-col border-r border-gray-200 bg-white">
    <!-- Logo -->
    <div class="flex h-16 items-center border-b border-gray-200 px-6">
      <component :is="MessageSquare" class="h-6 w-6 text-gray-900" />
      <span class="ml-3 text-lg font-normal text-gray-900">
        Bingo AI
      </span>
    </div>

    <!-- New Chat Button -->
    <div>
      <button
        @click="handleNewChat"
        class="flex w-full items-center gap-2 px-4 py-3 text-sm font-extralight text-gray-700 hover:bg-gray-100"
      >
        <span class="flex h-5 w-5 items-center justify-center rounded-full bg-gray-900">
          <Plus class="h-3 w-3 text-white" />
        </span>
        New Chat
      </button>
    </div>

    <!-- Conversation List -->
    <div class="flex-1 overflow-y-auto">
      <!-- Recent section header -->
      <button
        @click="isRecentExpanded = !isRecentExpanded"
        class="flex w-full items-center gap-2 px-4 py-2 text-xs font-extralight uppercase tracking-wider text-gray-400 hover:text-gray-600"
      >
        <ChevronDown v-if="isRecentExpanded" class="h-3.5 w-3.5" />
        <ChevronRight v-else class="h-3.5 w-3.5" />
        Recent
      </button>

      <!-- Conversation list (collapsible) -->
      <div v-show="isRecentExpanded">
        <div v-if="chatStore.conversations.length === 0" class="px-4 py-4 text-center text-sm text-gray-500">
          No conversations yet
        </div>
        <button
          v-for="conv in chatStore.conversations"
          :key="conv.id"
          @click="handleSelectConversation(conv.id)"
          class="w-full rounded-lg px-4 py-0.5 text-left text-sm hover:bg-gray-50"
          :class="chatStore.currentThreadId === conv.id ? 'bg-gray-100' : ''"
        >
          <div class="font-extralight text-gray-500 truncate">{{ conv.title }}</div>
        </button>
      </div>
    </div>

    <!-- User account button -->
    <button
      @click="router.push('/settings')"
      class="border-t border-gray-200 px-4 py-5 hover:bg-gray-50 transition-colors w-full text-left"
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
import { MessageSquare, Settings, Plus, ChevronDown, ChevronRight } from 'lucide-vue-next'

const authStore = useAuthStore()
const chatStore = useChatStore()
const chat = useChat()
const router = useRouter()
const route = useRoute()

const isRecentExpanded = ref(true)

const userInitial = computed(() => {
  const email = authStore.user?.email || ''
  return email.charAt(0).toUpperCase()
})

// Load conversations on mount
onMounted(() => {
  chat.loadConversations()
})

const handleNewChat = () => {
  chat.newChat()
  // Navigate to chat page if not already there
  if (route.path !== '/chat') {
    navigateTo('/chat')
  }
}

const handleSelectConversation = (id: string) => {
  chat.loadMessages(id)
  // Navigate to chat page if not already there
  if (route.path !== '/chat') {
    navigateTo('/chat')
  }
}

const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 60) return `${diffMins}m ago`
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
  return `${Math.floor(diffMins / 1440)}d ago`
}
</script>
