<template>
  <div class="w-full md:w-[420px] flex-shrink-0 border-l border-gray-200 flex flex-col h-full overflow-hidden bg-white dark:bg-neutral-900 dark:border-neutral-700">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-neutral-700 flex-shrink-0">
      <div class="flex items-center gap-2">
        <BarChart2 class="h-4 w-4 text-indigo-500" />
        <span class="text-sm font-semibold text-gray-800 dark:text-neutral-100">Dashboard Analysis</span>
      </div>
      <button
        class="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors dark:text-neutral-500 dark:hover:text-neutral-300 dark:hover:bg-neutral-800"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <div class="relative">
        <div class="h-10 w-10 rounded-full border-2 border-indigo-100 dark:border-indigo-900/40" />
        <div class="absolute inset-0 h-10 w-10 rounded-full border-2 border-transparent border-t-indigo-500 animate-spin" />
      </div>
      <p class="text-sm text-gray-500 dark:text-neutral-400">Analyzing dashboard…</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <AlertCircle class="h-8 w-8 text-red-400" />
      <p class="text-sm text-gray-600 dark:text-neutral-300">{{ error }}</p>
      <button
        class="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
        @click="emit('retry')"
      >Try again</button>
    </div>

    <!-- Result -->
    <div v-else-if="message" class="flex-1 min-h-0 overflow-y-auto px-4 py-4">
      <UiMarkdownRenderer :content="message" class="text-sm" />
    </div>

    <!-- Empty / initial state -->
    <div v-else class="flex flex-1 flex-col items-center justify-center gap-2 px-6 text-center">
      <BarChart2 class="h-8 w-8 text-gray-300 dark:text-neutral-600" />
      <p class="text-sm text-gray-400 dark:text-neutral-500">No analysis yet</p>
    </div>

    <!-- Footer timestamp -->
    <div v-if="message && !loading" class="px-4 py-2.5 border-t border-gray-100 dark:border-neutral-700 flex-shrink-0">
      <p class="text-xs text-gray-400 dark:text-neutral-500">Analyzed {{ analysisTime }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BarChart2, X, AlertCircle } from 'lucide-vue-next'

const props = defineProps<{
  loading: boolean
  message: string
  error: string
}>()

const emit = defineEmits<{
  close: []
  retry: []
}>()

const analysisTime = computed(() => {
  const now = new Date()
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
})
</script>
