<template>
  <div class="flex h-full flex-col overflow-hidden">
    <div class="flex-1 overflow-auto">
      <table class="w-full text-sm">
        <thead class="sticky top-0 bg-white border-b border-gray-100">
          <tr>
            <th
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 text-left text-xs font-medium text-gray-400 uppercase tracking-wide whitespace-nowrap"
              :class="col.sortable ? 'cursor-pointer hover:text-gray-600 select-none' : ''"
              @click="col.sortable && toggleSort(col.key)"
            >
              <div class="flex items-center gap-1">
                {{ col.label }}
                <span v-if="col.sortable && sortKey === col.key" class="text-gray-500">
                  {{ sortDir === 'asc' ? '↑' : '↓' }}
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <tr
            v-for="(row, i) in sortedRows"
            :key="i"
            class="hover:bg-gray-50 transition-colors"
          >
            <td
              v-for="col in config.columns"
              :key="col.key"
              class="px-4 py-2.5 text-gray-700 whitespace-nowrap"
              :class="col.format === 'currency' || col.format === 'number' || col.format === 'percent' ? 'tabular-nums' : ''"
            >
              <span :class="getCellClass(row[col.key], col.format)">
                {{ formatCell(row[col.key], col.format) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TableWidgetConfig } from '~/types/dashboard'

const props = defineProps<{
  config: TableWidgetConfig
}>()

const sortKey = ref<string | null>(null)
const sortDir = ref<'asc' | 'desc'>('asc')

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}

const sortedRows = computed(() => {
  if (!sortKey.value) return props.config.rows
  const key = sortKey.value
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...props.config.rows].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av == null) return 1
    if (bv == null) return -1
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

function formatCell(value: any, format?: string): string {
  if (value == null) return '—'
  switch (format) {
    case 'currency':
      return '$' + Number(value).toLocaleString()
    case 'number':
      return Number(value).toLocaleString()
    case 'percent':
      return (value > 0 ? '+' : '') + Number(value).toFixed(1) + '%'
    case 'date':
      return new Date(value).toLocaleDateString()
    default:
      return String(value)
  }
}

function getCellClass(value: any, format?: string): string {
  if (format === 'percent' && typeof value === 'number') {
    return value > 0 ? 'text-emerald-600' : value < 0 ? 'text-rose-500' : ''
  }
  return ''
}
</script>
