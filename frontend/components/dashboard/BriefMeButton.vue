<template>
  <button class="hdr-btn" :disabled="busy" @click="onClick">
    <Sparkles class="h-3.5 w-3.5" />
    <span class="hidden sm:inline">{{ busy ? 'Briefing…' : 'Brief me' }}</span>
  </button>
</template>

<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'

const props = defineProps<{ dashboardId: number }>()
const busy = ref(false)
const { fetchWithRefresh } = useApi()
const { refresh: refreshBriefingsList } = useBriefingsList()

async function onClick() {
  busy.value = true
  try {
    const resp = await fetchWithRefresh(
      `/api/dashboards/${props.dashboardId}/brief`,
      { method: 'POST' },
    )
    refreshBriefingsList()
    navigateTo(`/chat?briefing=${resp.briefing_id}`)
  } finally {
    busy.value = false
  }
}
</script>
