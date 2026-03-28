<template>
  <div class="relative flex h-screen bg-white">
    <!-- Mobile backdrop overlay (shown when sidebar visible on mobile) -->
    <div
      v-if="isMobile && !layoutStore.isMainExpanded"
      class="fixed inset-0 z-30 bg-black/30"
      @click="layoutStore.setMainExpanded(true)"
    />

    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content panel - expands leftward over sidebar -->
    <main
      class="absolute inset-y-0 right-0 z-20 flex flex-col overflow-hidden bg-white shadow-2xl transition-[width] duration-300 ease-in-out"
      :class="layoutStore.isMainExpanded || isMobile ? 'w-full' : 'w-[calc(100%-250px)]'"
    >
      <!-- Toggle button inside main, top-left -->
      <button
        @click="layoutStore.toggleMainExpand()"
        class="absolute left-3 top-1.5 z-30 rounded-lg p-2 pt-4 ml-1 transition-colors"
        :aria-label="layoutStore.isMainExpanded ? 'Show sidebar' : 'Hide sidebar'"
      >
        <Menu v-if="isMobile && layoutStore.isMainExpanded" class="h-6 w-6 text-gray-600" />
        <PanelLeftOpen v-else-if="layoutStore.isMainExpanded" class="h-6 w-6 text-gray-600" />
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
import { PanelLeftClose, PanelLeftOpen, Archive, Menu } from 'lucide-vue-next'

const authStore = useAuthStore()
const layoutStore = useLayoutStore()
const chatStore = useChatStore()
const chat = useChat()
const route = useRoute()
const { isMobile } = useIsMobile()

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

// On mobile, ensure sidebar is hidden. immediate: true catches initial load,
// and subsequent changes handle resize/orientation
watch(isMobile, (mobile) => {
  if (mobile && !layoutStore.isMainExpanded) {
    layoutStore.setMainExpanded(true)
  }
}, { immediate: true })
</script>
