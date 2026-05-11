<template>
  <div class="w-full md:w-[420px] flex-shrink-0 border-l border-gray-200 flex flex-col h-full overflow-hidden bg-white dark:bg-neutral-900 dark:border-neutral-700">
    <!-- Header -->
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-neutral-700 flex-shrink-0">
      <div class="flex items-center gap-2">
        <BarChart2 class="h-4 w-4 text-indigo-500" />
        <span class="text-sm font-semibold text-gray-800 dark:text-neutral-100">Brief this dashboard</span>
      </div>
      <button
        class="p-1 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors dark:text-neutral-500 dark:hover:text-neutral-300 dark:hover:bg-neutral-800"
        @click="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto">
      <template v-if="briefingId">
        <BriefingCard :briefing-id="briefingId" />
        <div class="px-4 pb-4">
          <NuxtLink
            :to="`/chat?briefing=${briefingId}`"
            class="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 inline-flex items-center gap-1"
          >
            <ExternalLink class="h-3.5 w-3.5" />
            Open full reading view
          </NuxtLink>
        </div>
      </template>
      <template v-else>
        <div class="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-12 text-center">
          <FileText class="h-10 w-10 text-gray-300 dark:text-neutral-600" />
          <p class="text-sm text-gray-500 dark:text-neutral-400 max-w-xs">
            Generate an AI-powered briefing for this dashboard. We'll analyze all widgets and create a readable report.
          </p>
          <button
            class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            :disabled="busy"
            @click="handleBrief"
          >
            <Loader2 v-if="busy" class="h-4 w-4 animate-spin" />
            <Sparkles v-else class="h-4 w-4" />
            {{ busy ? 'Creating briefing…' : 'Brief this dashboard' }}
          </button>
          <p v-if="error" class="text-xs text-red-500">{{ error }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { BarChart2, X, FileText, Sparkles, Loader2, ExternalLink } from 'lucide-vue-next'

const props = defineProps<{
  dashboardId: number
}>()

const emit = defineEmits<{
  close: []
}>()

const { dashboards: dashboardsApi } = useApi()

const busy = ref(false)
const error = ref('')
const briefingId = ref<number | null>(null)

async function handleBrief() {
  busy.value = true
  error.value = ''
  try {
    const result = await dashboardsApi.brief(props.dashboardId)
    briefingId.value = result.briefing_id
  } catch {
    error.value = 'Failed to create briefing. Please try again.'
  } finally {
    busy.value = false
  }
}
</script>
