<template>
  <div class="flex h-full flex-wrap items-center gap-3 p-3">
    <div
      v-for="control in config.controls"
      :key="control.key"
      class="flex items-center gap-2"
    >
      <label class="text-xs font-medium text-gray-500 whitespace-nowrap">{{ control.label }}</label>
      <select
        v-if="control.type === 'dropdown'"
        class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none"
      >
        <option value="">All</option>
        <option v-for="opt in control.options" :key="opt" :value="opt">{{ opt }}</option>
      </select>
      <input
        v-else-if="control.type === 'search'"
        type="text"
        placeholder="Search..."
        class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none w-36"
      />
      <div
        v-else-if="control.type === 'date_range'"
        class="flex items-center gap-1.5"
      >
        <input type="date" class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none" />
        <span class="text-xs text-gray-400">to</span>
        <input type="date" class="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-700 focus:border-gray-400 focus:outline-none" />
      </div>
    </div>
    <div v-if="config.controls.length === 0" class="flex items-center gap-2 text-xs text-gray-400">
      <SlidersHorizontal class="h-3.5 w-3.5" />
      <span>No filters configured</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { SlidersHorizontal } from 'lucide-vue-next'
import type { FilterWidgetConfig } from '~/types/dashboard'

defineProps<{
  config: FilterWidgetConfig
}>()
</script>
