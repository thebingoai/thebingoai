<template>
  <div class="flex flex-1 overflow-hidden">
    <!-- Main dashboard grid area -->
    <div class="flex flex-1 flex-col items-center justify-center min-w-0 min-h-0">
      <component :is="LayoutGrid" class="h-10 w-10 text-gray-200 mb-3" />
      <p class="text-sm font-light text-gray-400">No dashboards yet</p>
    </div>

    <!-- Right-side vertical tabs -->
    <div class="flex w-14 flex-shrink-0 flex-col border-l border-gray-200 bg-white py-3">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="activeTab = tab.id"
        class="flex flex-col items-center gap-1 px-1 py-3 transition-colors"
        :class="activeTab === tab.id ? 'text-gray-900' : 'text-gray-400 hover:text-gray-600'"
      >
        <div
          class="flex h-7 w-7 items-center justify-center rounded-lg transition-colors"
          :class="activeTab === tab.id ? 'bg-gray-100' : ''"
        >
          <component :is="tab.icon" class="h-4 w-4" />
        </div>
        <span class="text-[10px] font-light leading-none">{{ tab.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { LayoutGrid, BarChart3, Activity } from 'lucide-vue-next'

const tabs = [
  { id: 'all', label: 'All', icon: LayoutGrid },
  { id: 'charts', label: 'Charts', icon: BarChart3 },
  { id: 'live', label: 'Live', icon: Activity },
]

const activeTab = ref('all')

definePageMeta({
  middleware: 'auth'
})
</script>
