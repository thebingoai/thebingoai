<template>
  <div class="border-b border-gray-100">
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('datasets')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Datasets</span>
        <span v-if="datasets.length" class="text-[9px] bg-gray-100 text-gray-500 px-1.5 py-px rounded-full">
          {{ datasets.length }}
        </span>
      </div>
      <svg
        class="w-3 h-3 text-gray-300 transition-transform duration-200"
        :class="{ 'rotate-180': chatStore.infoPanelSections.datasets }"
        fill="none" viewBox="0 0 24 24" stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Content -->
    <div v-show="chatStore.infoPanelSections.datasets" class="px-4 pb-3">
      <!-- Empty state -->
      <div v-if="!datasets.length" class="text-center py-4">
        <svg class="w-5 h-5 mx-auto text-gray-200 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p class="text-[11px] text-gray-300">No datasets uploaded yet</p>
      </div>

      <!-- Dataset list -->
      <div v-else class="flex flex-col gap-1.5">
        <div
          v-for="ds in datasets"
          :key="ds.fileId ?? ds.name"
          class="flex items-center gap-2 rounded-lg bg-gray-50 px-2.5 py-2"
        >
          <svg class="w-4 h-4 text-gray-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <div class="min-w-0 flex-1">
            <p class="text-[11px] font-medium text-gray-600 truncate">{{ ds.name }}</p>
            <p class="text-[10px] text-gray-300">{{ formatSize(ds.size) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const chatStore = useChatStore()

const datasets = computed(() => chatStore.conversationDatasets)

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>
