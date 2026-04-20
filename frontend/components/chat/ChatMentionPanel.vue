<template>
  <div class="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg overflow-hidden">
    <!-- Real search input -->
    <div class="px-3 py-2 border-b border-gray-100 dark:border-neutral-700 flex items-center gap-2">
      <Search class="h-4 w-4 text-gray-400 dark:text-neutral-500 shrink-0" />
      <input
        ref="searchRef"
        :value="mentionQuery"
        @input="setQuery(($event.target as HTMLInputElement).value)"
        @keydown="handleKeydown"
        placeholder="Search dashboards & connections…"
        class="flex-1 text-sm bg-transparent outline-none text-gray-700 dark:text-neutral-200 placeholder-gray-400 dark:placeholder-neutral-500 min-w-0"
        autocomplete="off"
      />
      <button
        type="button"
        class="text-gray-400 dark:text-neutral-500 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors"
        @mousedown.prevent="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Results list -->
    <div class="max-h-60 overflow-y-auto">
      <!-- Dashboards -->
      <template v-if="props.filteredResults.dashboards.length">
        <div class="px-3 pt-2 pb-1 text-xs font-semibold text-gray-400 dark:text-neutral-500 uppercase tracking-wider select-none">
          Dashboards
        </div>
        <button
          v-for="(item, i) in props.filteredResults.dashboards"
          :key="`d-${item.id}`"
          type="button"
          class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors"
          :class="flatIndex(i, 'dashboard') === activeIndex
            ? 'bg-gray-100 dark:bg-neutral-700 text-gray-900 dark:text-white'
            : 'text-gray-700 dark:text-neutral-200 hover:bg-gray-50 dark:hover:bg-neutral-700/50'"
          @mousedown.prevent="emit('select', item)"
        >
          <LayoutDashboard class="h-4 w-4 text-purple-500 shrink-0" />
          <span class="truncate">{{ item.displayName }}</span>
          <span class="ml-auto text-xs text-gray-400 dark:text-neutral-500 shrink-0 font-mono">@{{ item.name }}</span>
        </button>
      </template>

      <!-- Connections -->
      <template v-if="props.filteredResults.connections.length">
        <div class="px-3 pt-2 pb-1 text-xs font-semibold text-gray-400 dark:text-neutral-500 uppercase tracking-wider select-none">
          Connections
        </div>
        <button
          v-for="(item, i) in props.filteredResults.connections"
          :key="`c-${item.id}`"
          type="button"
          class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors"
          :class="flatIndex(i, 'connection') === activeIndex
            ? 'bg-gray-100 dark:bg-neutral-700 text-gray-900 dark:text-white'
            : 'text-gray-700 dark:text-neutral-200 hover:bg-gray-50 dark:hover:bg-neutral-700/50'"
          @mousedown.prevent="emit('select', item)"
        >
          <Database class="h-4 w-4 text-blue-500 shrink-0" />
          <span class="truncate">{{ item.displayName }}</span>
          <span v-if="item.dbType" class="ml-auto text-xs text-gray-400 dark:text-neutral-500 shrink-0">{{ item.dbType }}</span>
        </button>
      </template>

      <!-- Empty state -->
      <div
        v-if="!props.filteredResults.dashboards.length && !props.filteredResults.connections.length"
        class="px-3 py-5 text-sm text-gray-400 dark:text-neutral-500 text-center"
      >
        No matches
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search, X, LayoutDashboard, Database } from 'lucide-vue-next'
import type { MentionItem } from '~/composables/useMentions'

const props = defineProps<{
  filteredResults: { dashboards: MentionItem[]; connections: MentionItem[] }
}>()

const emit = defineEmits<{
  select: [item: MentionItem]
  close: []
}>()

const searchRef = ref<HTMLInputElement | null>(null)
const { mentionQuery, setQuery } = useMentions()

// Active item index across the flat [dashboards..., connections...] list
const activeIndex = ref(0)

const allItems = computed((): MentionItem[] => [
  ...props.filteredResults.dashboards,
  ...props.filteredResults.connections,
])

// Reset active index when results change
watch(() => props.filteredResults, () => { activeIndex.value = 0 })

// Autofocus the search input when the panel mounts
onMounted(() => nextTick(() => searchRef.value?.focus()))

// Map per-section index → flat index
const flatIndex = (sectionIdx: number, type: 'dashboard' | 'connection') =>
  type === 'dashboard'
    ? sectionIdx
    : props.filteredResults.dashboards.length + sectionIdx

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, allItems.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const item = allItems.value[activeIndex.value]
    if (item) emit('select', item)
  } else if (e.key === 'Escape') {
    e.preventDefault()
    emit('close')
  }
}
</script>
