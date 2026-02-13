<template>
  <aside class="flex w-sidebar flex-col border-r border-gray-200 bg-white">
    <!-- Logo -->
    <div class="flex h-16 items-center border-b border-gray-200 px-6">
      <component :is="MessageSquare" class="h-6 w-6 text-gray-900" />
      <span class="ml-3 text-lg font-semibold text-gray-900">
        BI Agent
      </span>
    </div>

    <!-- New Chat Button -->
    <div class="border-b border-gray-200 p-4">
      <UiButton variant="primary" full-width @click="handleNewChat">
        + New Chat
      </UiButton>
    </div>

    <!-- Conversation List -->
    <div class="flex-1 overflow-y-auto p-2">
      <div v-if="chatStore.conversations.length === 0" class="p-4 text-center text-sm text-gray-500">
        No conversations yet
      </div>
      <button
        v-for="conv in chatStore.conversations"
        :key="conv.id"
        @click="handleSelectConversation(conv.id)"
        class="mb-1 w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-gray-50"
        :class="chatStore.currentThreadId === conv.id ? 'bg-gray-100' : ''"
      >
        <div class="font-medium text-gray-900 truncate">{{ conv.title }}</div>
        <div class="text-xs text-gray-500">{{ formatDate(conv.created_at) }}</div>
      </button>
    </div>

    <!-- User account button -->
    <button
      @click="router.push('/settings')"
      class="border-t border-gray-200 p-4 hover:bg-gray-50 transition-colors w-full text-left"
    >
      <div class="flex items-center">
        <div class="flex h-10 w-10 items-center justify-center rounded-full bg-gray-900 text-white text-sm font-medium">
          {{ userInitial }}
        </div>
        <div class="ml-3 flex-1 min-w-0">
          <p class="text-sm font-medium text-gray-900 truncate">{{ authStore.user?.email }}</p>
          <p class="text-xs text-gray-500">View settings</p>
        </div>
        <component :is="Settings" class="h-4 w-4 text-gray-400" />
      </div>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { MessageSquare, Settings } from 'lucide-vue-next'

const authStore = useAuthStore()
const chatStore = useChatStore()
const chat = useChat()
const router = useRouter()
const route = useRoute()

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
