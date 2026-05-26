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

const emit = defineEmits<{ loaded: [] }>()

const { fetchWithRefresh } = useApi()
const widget = ref<any>(null)
// DashboardWidget only refreshes on click; briefing embeds render the saved
// (data-less) config. Pull the widget's data on mount so charts/KPIs populate.
const { refresh } = useWidgetData(widget as any)

onMounted(async () => {
  try {
    widget.value = await fetchWithRefresh(
      `/api/dashboards/${props.dashboardId}/widgets/${props.widgetId}`,
      { method: 'GET' },
    )
    if (widget.value?.dataSource) {
      await refresh()
    }
  } catch {
    // widget deleted between briefing-time and view-time — silent drop
    widget.value = null
  } finally {
    // Always signal completion — even a dropped widget must not stall the PDF wait.
    emit('loaded')
  }
})
</script>
