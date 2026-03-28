<template>
  <div class="relative flex h-screen bg-white">
    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content panel - expands leftward over sidebar -->
    <main
      class="absolute inset-y-0 right-0 z-20 flex flex-col overflow-hidden bg-white shadow-2xl transition-[width] duration-300 ease-in-out"
      :class="layoutStore.isMainExpanded ? 'w-full' : 'w-[calc(100%-250px)]'"
    >
      <!-- Toggle button inside main, top-left -->
      <button
        @click="layoutStore.toggleMainExpand()"
        class="absolute left-3 top-1.5 z-30 rounded-lg p-2 pt-4 ml-1 transition-colors"
        :aria-label="layoutStore.isMainExpanded ? 'Show sidebar' : 'Hide sidebar'"
      >
        <PanelLeftOpen v-if="layoutStore.isMainExpanded" class="h-6 w-6 text-gray-600" />
        <PanelLeftClose v-else class="h-6 w-6 text-gray-600" />
      </button>

      <!-- Archive button inside main, top-right -->
      <button
        v-if="canArchive"
        @click="handleArchive"
        class="absolute right-3 top-1.5 z-30 rounded-lg p-2 pt-4 mr-1 transition-colors hover:bg-gray-100"
        aria-label="Archive conversation"
      >
        <Archive class="h-5 w-5 text-gray-500 hover:text-gray-700" />
      </button>

      <div class="flex flex-1 flex-col overflow-hidden pt-12">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { PanelLeftClose, PanelLeftOpen, Archive } from 'lucide-vue-next'

const authStore = useAuthStore()
const layoutStore = useLayoutStore()
const chatStore = useChatStore()
const chat = useChat()
const route = useRoute()

const canArchive = computed(() => {
  if (route.path !== '/chat') return false
  if (chatStore.isStreaming) return false
  const current = chatStore.currentConversation
  return current && current.type === 'task'
})

const handleArchive = () => {
  if (chatStore.currentThreadId) {
    chat.archiveConversation(chatStore.currentThreadId)
  }
}

// Load user on mount
onMounted(() => {
  if (process.client) {
    authStore.loadUser()
  }
})
</script>
