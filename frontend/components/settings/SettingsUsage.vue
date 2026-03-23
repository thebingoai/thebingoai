<template>
  <div class="p-6">
    <h2 class="text-2xl font-medium text-gray-900 mb-6">Usage</h2>

    <UiCard class="p-6">
      <h3 class="text-lg font-medium text-gray-900 mb-4">Token Usage (30 days)</h3>

      <div v-if="loading" class="space-y-3">
        <UiSkeleton class="h-4 w-48" />
        <UiSkeleton class="h-4 w-36" />
      </div>

      <div v-else class="space-y-3">
        <div class="flex items-center justify-between text-sm">
          <span class="text-gray-600">Input tokens</span>
          <span class="font-medium text-gray-900">{{ inputTokens.toLocaleString() }}</span>
        </div>
        <div class="flex items-center justify-between text-sm">
          <span class="text-gray-600">Output tokens</span>
          <span class="font-medium text-gray-900">{{ outputTokens.toLocaleString() }}</span>
        </div>
      </div>
    </UiCard>
  </div>
</template>

<script setup lang="ts">
const api = useApi()

interface UsageSummary {
  totals: { input_tokens: number; output_tokens: number }
}

const loading = ref(true)
const summary = ref<UsageSummary | null>(null)

const inputTokens = computed(() => summary.value?.totals.input_tokens ?? 0)
const outputTokens = computed(() => summary.value?.totals.output_tokens ?? 0)

onMounted(async () => {
  try {
    summary.value = await api.usage.getSummary(30) as UsageSummary
  } catch (e) {
    console.error('Failed to load usage summary:', e)
  } finally {
    loading.value = false
  }
})
</script>
