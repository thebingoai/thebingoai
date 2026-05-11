<template>
  <div v-if="widget" class="rounded-lg border border-neutral-100 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4">
    <DashboardWidget :widget="widget" />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  widgetId: string | number
  dashboardId: number
}>()

const { fetchWithRefresh } = useApi()
const widget = ref<any>(null)

onMounted(async () => {
  try {
    widget.value = await fetchWithRefresh(
      `/api/dashboards/${props.dashboardId}/widgets/${props.widgetId}`,
      { method: 'GET' },
    )
  } catch {
    // widget deleted between briefing-time and view-time — silent drop
    widget.value = null
  }
})
</script>
