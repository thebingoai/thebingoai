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

      <div class="flex flex-1 flex-col overflow-hidden pt-12">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'

const authStore = useAuthStore()
const layoutStore = useLayoutStore()

// Load user on mount
onMounted(() => {
  if (process.client) {
    authStore.loadUser()
  }
})
</script>
