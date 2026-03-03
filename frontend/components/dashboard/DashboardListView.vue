<template>
  <div class="flex flex-1 flex-col min-h-0">
    <div v-if="items.length > 0" class="grid gap-5 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
      <DashboardCard
        v-for="item in items"
        :key="item.id"
        :dashboard="item"
        @click="emit('open', item.id)"
      />
    </div>
    <div v-else class="flex flex-1 flex-col items-center justify-center min-h-[400px]">
      <LayoutGrid class="h-10 w-10 text-gray-200 mb-3" />
      <p class="text-sm font-light text-gray-400">No dashboards yet</p>
      <p class="text-xs text-gray-300 mt-1">Ask the AI to generate one or create it manually</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { LayoutGrid } from 'lucide-vue-next'
import type { DashboardListItem } from '~/types/dashboard'

defineProps<{
  items: DashboardListItem[]
}>()

const emit = defineEmits<{
  open: [id: string]
}>()
</script>
