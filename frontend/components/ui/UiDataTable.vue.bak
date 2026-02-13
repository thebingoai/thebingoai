<template>
  <div class="w-full overflow-hidden rounded-lg border border-neutral-200 dark:border-neutral-800">
    <div class="overflow-x-auto">
      <table class="w-full">
        <thead class="border-b border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-900">
          <tr>
            <th
              v-if="selectable"
              class="px-4 py-3 text-left"
            >
              <input
                type="checkbox"
                :checked="isAllSelected"
                @change="toggleSelectAll"
                class="h-4 w-4 rounded border-neutral-300 text-brand-600 focus:ring-brand-500 dark:border-neutral-700"
              />
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-neutral-700 dark:text-neutral-300"
              :class="column.sortable && 'cursor-pointer select-none hover:bg-neutral-100 dark:hover:bg-neutral-800'"
              @click="column.sortable && handleSort(column.key)"
            >
              <div class="flex items-center gap-2">
                {{ column.label }}
                <component
                  v-if="column.sortable && sortKey === column.key"
                  :is="sortDirection === 'asc' ? ArrowUp : ArrowDown"
                  class="h-4 w-4"
                />
              </div>
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-neutral-200 dark:divide-neutral-800">
          <tr
            v-for="(row, index) in sortedData"
            :key="index"
            class="transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            <td v-if="selectable" class="px-4 py-3">
              <input
                type="checkbox"
                :checked="selectedRows.has(index)"
                @change="toggleRow(index)"
                class="h-4 w-4 rounded border-neutral-300 text-brand-600 focus:ring-brand-500 dark:border-neutral-700"
              />
            </td>
            <td
              v-for="column in columns"
              :key="column.key"
              class="px-4 py-3 text-sm text-neutral-900 dark:text-neutral-100"
            >
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                {{ row[column.key] }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="data.length === 0" class="py-12 text-center text-sm text-neutral-500 dark:text-neutral-400">
      No data available
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowUp, ArrowDown } from 'lucide-vue-next'

export interface TableColumn {
  key: string
  label: string
  sortable?: boolean
}

interface Props {
  columns: TableColumn[]
  data: Record<string, any>[]
  selectable?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selectable: false
})

const emit = defineEmits<{
  'selection-change': [selectedIndices: number[]]
}>()

const sortKey = ref<string | null>(null)
const sortDirection = ref<'asc' | 'desc'>('asc')
const selectedRows = ref(new Set<number>())

const sortedData = computed(() => {
  if (!sortKey.value) return props.data

  return [...props.data].sort((a, b) => {
    const aVal = a[sortKey.value!]
    const bVal = b[sortKey.value!]

    if (aVal === bVal) return 0

    const comparison = aVal < bVal ? -1 : 1
    return sortDirection.value === 'asc' ? comparison : -comparison
  })
})

const isAllSelected = computed(() => {
  return props.data.length > 0 && selectedRows.value.size === props.data.length
})

const handleSort = (key: string) => {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDirection.value = 'asc'
  }
}

const toggleRow = (index: number) => {
  if (selectedRows.value.has(index)) {
    selectedRows.value.delete(index)
  } else {
    selectedRows.value.add(index)
  }
  emit('selection-change', Array.from(selectedRows.value))
}

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    selectedRows.value.clear()
  } else {
    selectedRows.value = new Set(props.data.map((_, i) => i))
  }
  emit('selection-change', Array.from(selectedRows.value))
}
</script>
